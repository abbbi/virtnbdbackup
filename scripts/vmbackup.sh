#!/usr/bin/env bash
#
# Copyright (C) 2024  Michael Ablassmeier
# Copyright (C) 2024  Sentry0
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
# ---
#
# Will perform an incremental backup (if possible) of a running or stopped VM 
# and deposit it into a monthly backup directory.  On the 15th of the current 
# month, the previous months' snapshots are deleted. This means there will be 
# about 2-6 weeks of backups at any given time.

# Creates a lock so that only one instance of this script may be executed
[ "${FLOCKER}" != "$0" ] && exec env FLOCKER="$0" flock -xn "$0" "$0" "$@" || :

print_help () {
    printf "Performs an incremental backup (if possible) on the given VMs.\n\n"
    printf "Usage:\n  -v [VM_NAMES]\n  -o [PATH]\n\n"
    printf "Example: %s -v vm1,vm2,vm3 -o /tmp/backups\n" "$0"
}

BACKUP_DIR=""

while getopts ':v:o:h' OPTION; do
    case "$OPTION" in
        v)
            IFS=',' read -r -a VMs <<< "$OPTARG"
        ;;
        o) 
            BACKUP_DIR=$OPTARG
        ;;
        h)
            print_help
            exit 0
        ;;
        \?)
            printf "Invalid usage: \n\n-v [VM_NAMES] \n\n-o [PATH]\n\n"
            print_help
        ;;
    esac
done

if [ ${#VMs[@]} -eq 0 ]; then
    print_help
    exit 1
fi

BACKUP_TOOL=$(which virtnbdbackup)

if [ ! -e "$BACKUP_DIR" ]; then
    mkdir -p "$BACKUP_DIR"
fi

if [ -z "${BACKUP_TOOL}" ]; then
    printf "Could not find virtnbdbackup.\n\n"
    printf "https://github.com/abbbi/virtnbdbackup\n"
    exit 2 
fi

DAY_OF_MONTH=$(date +'%d')
SNAPSHOT_NAME=$(date +'%Y-%m')
EXITCODE=0

# Backup all the VMs, running or stopped, incrementally if possible
for name in "${VMs[@]}"; do
    SNAPSHOT_PATH=${BACKUP_DIR}/${name}/${SNAPSHOT_NAME}
    printf "Backing up %s to %s\n" "$name" "${SNAPSHOT_PATH}"

    "${BACKUP_TOOL}" -S --noprogress -d "${name}" -l auto -o "${SNAPSHOT_PATH}"

    # Delete last month's backups if our latest backup succeeded and it is the
    # middle of the current month.
    if [ $? -eq 0 ] && [ "$DAY_OF_MONTH" -eq 15 ]; then
        LAST_MONTH=$(date -d "$(date +%Y-%m-1) -1 month" +%Y-%m)
    	LAST_MONTHS_BACKUPS_DIR=${BACKUP_DIR}/${name}/${LAST_MONTH}

        if [ -d "${LAST_MONTHS_BACKUPS_DIR}" ]; then
            printf "Removing backups for %s for %s" "${name}" "${LAST_MONTH}"
            rm -rf "${LAST_MONTHS_BACKUPS_DIR}"
        fi
    else
        ((EXITCODE=EXITCODE+1))
    fi
done

exit $EXITCODE
