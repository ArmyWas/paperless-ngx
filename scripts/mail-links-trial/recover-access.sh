#!/usr/bin/env bash
# Restore browser access to an existing disposable trial without clearing its data.
set -euo pipefail

recovery_tag=mail-links-trial-20261113-access1
project=${MAIL_LINKS_TRIAL_PROJECT:-paperless-mail-links-trial}
port=${MAIL_LINKS_TRIAL_PORT:-8088}
compose_file=compose.access-fixed.yaml
compose_temp=
resolved_temp=
nginx_temp=

fail() {
	printf 'STOP: %s\n' "$*" >&2
	exit 1
}

cleanup() {
	local status=$?
	if [[ -n "$compose_temp" ]]; then
		rm -f -- "$compose_temp"
	fi
	if [[ -n "$nginx_temp" ]]; then
		rm -f -- "$nginx_temp"
	fi
	if [[ -n "$resolved_temp" ]]; then
		rm -f -- "$resolved_temp"
	fi
	if ((status != 0)); then
		printf '%s\n' 'Recovery did not finish. Keep the existing volumes and documents; do not rerun the fresh-instance import script.' >&2
	fi
}
trap cleanup EXIT

for tool in git docker mktemp; do
	command -v "$tool" >/dev/null 2>&1 || fail "Required command is missing: $tool"
done
[[ $(git rev-parse --show-prefix) == scripts/mail-links-trial/ ]] ||
	fail 'Run this script from the original checkout scripts/mail-links-trial directory.'
[[ -f compose.yaml && -f smoke.py ]] ||
	fail 'The original compose.yaml and smoke.py must still be in this directory.'
[[ "$project" =~ ^[a-z0-9][a-z0-9_-]*$ ]] || fail 'Invalid trial project name.'
[[ "$port" =~ ^[0-9]{1,5}$ ]] || fail 'Invalid local trial port.'
((10#$port >= 1 && 10#$port <= 65535)) || fail 'The local trial port must be between 1 and 65535.'
docker compose version >/dev/null
git rev-parse --verify "refs/tags/$recovery_tag^{commit}" >/dev/null ||
	fail "The recovery tag is missing. Fetch tag $recovery_tag before running this script."

# These overrides are for isolated validation projects, not production instances.
export MAIL_LINKS_TRIAL_PORT="$port"
container_ids=$(docker ps --all --quiet \
	--filter "label=com.docker.compose.project=$project" \
	--filter 'label=com.docker.compose.service=webserver' \
	--filter 'label=com.docker.compose.oneoff=False')
[[ -n "$container_ids" ]] || fail "No existing trial webserver was found for project $project."
mapfile -t containers <<<"$container_ids"
((${#containers[@]} == 1)) || fail 'More than one trial webserver was found; inspect the project before proceeding.'
container=${containers[0]}

# Reject a customized storage layout rather than silently opening a new database.
for volume in data media consume export; do
	destination="/usr/src/paperless/$volume"
	mount=$(docker inspect --format \
		"{{range .Mounts}}{{if eq .Destination \"$destination\"}}{{.Type}}:{{.Name}}{{end}}{{end}}" \
		"$container")
	[[ "$mount" == "volume:${project}_$volume" ]] ||
		fail "Unexpected storage at $destination ($mount). No configuration or container was changed."
	docker volume inspect "${project}_$volume" >/dev/null
done
image_id=$(docker inspect --format '{{.Image}}' "$container")
[[ "$image_id" == sha256:* ]] || fail 'Could not identify the existing application image.'
docker image inspect "$image_id" >/dev/null || fail 'The original application image is no longer available locally.'
export MAIL_LINKS_TRIAL_IMAGE="$image_id"

for target in "$compose_file" nginx.conf; do
	[[ ! -L "$target" && (! -e "$target" || -f "$target") ]] ||
		fail "Refusing to replace a symlink or non-file: $target"
done

compose_temp=$(mktemp .mail-links-compose.XXXXXX)
nginx_temp=$(mktemp .mail-links-nginx.XXXXXX)
git show "refs/tags/$recovery_tag:scripts/mail-links-trial/compose.yaml" >"$compose_temp"
git show "refs/tags/$recovery_tag:scripts/mail-links-trial/nginx.conf" >"$nginx_temp"
# Persist the exact local image, port and paths for subsequent start/stop commands.
resolved_temp=$(mktemp .mail-links-resolved.XXXXXX)
docker compose -p "$project" -f "$compose_temp" config >"$resolved_temp"
mv -- "$resolved_temp" "$compose_temp"
resolved_temp=
# The unprivileged proxy must be able to read its bind-mounted configuration.
chmod 644 "$compose_temp" "$nginx_temp"
docker compose -p "$project" -f "$compose_temp" config --quiet
resolved_images=$(docker compose -p "$project" -f "$compose_temp" config --images)
uses_original_image=false
while IFS= read -r resolved_image; do
	if [[ "$resolved_image" == "$image_id" ]]; then
		uses_original_image=true
	fi
done <<<"$resolved_images"
[[ "$uses_original_image" == true ]] || fail 'The recovery configuration would not use the original application image.'

# Preserve both any previous recovery files and the untouched original compose.yaml.
for target in "$compose_file" nginx.conf; do
	if [[ -f "$target" ]]; then
		backup=$(mktemp "$target.backup.XXXXXX")
		cp -p -- "$target" "$backup"
		printf 'Saved previous %s as %s\n' "$target" "$backup"
	fi
done
mv -- "$compose_temp" "$compose_file"
compose_temp=
mv -- "$nginx_temp" nginx.conf
nginx_temp=
printf '%s\n' 'Original compose.yaml preserved. All four existing data volumes will be reused.'
printf 'Reusing application image: %s\n' "$image_id"

# Download only the small access proxy. Never pull or rebuild the application.
docker compose -p "$project" -f "$compose_file" pull browser
docker compose -p "$project" -f "$compose_file" up \
	-d --no-build --pull never --wait --wait-timeout 300
docker compose -p "$project" -f "$compose_file" ps --all

url="http://127.0.0.1:$port"
printf '\nOpen %s\nUsername: trial\nPassword: mail-links-local-trial\n' "$url"
printf '%s\n' 'Existing data volumes were kept. Do not rerun smoke.py: its import step is for a fresh instance only.'
printf 'Use -p %s -f %s for future trial start/stop commands.\n' "$project" "$compose_file"

if command -v curl >/dev/null 2>&1; then
	if status=$(curl --noproxy '*' --fail --silent --show-error \
		--retry 3 --retry-connrefused --retry-delay 1 --max-time 10 \
		--output /dev/null --write-out '%{http_code}' "$url/accounts/login/") && [[ "$status" == 200 ]]; then
		printf '%s\n' 'Verified: the login page is reachable from this computer (HTTP 200).'
	else
		printf 'The services started, but the host login page is not yet verified. Run:\n  curl --noproxy '\''*'\'' --max-time 10 -v %s/accounts/login/\n' "$url" >&2
		exit 1
	fi
else
	printf 'If the page is unreachable, run in this same WSL/Linux terminal:\n  curl --noproxy '\''*'\'' --max-time 10 -v %s/accounts/login/\n' "$url"
fi
