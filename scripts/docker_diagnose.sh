#!/usr/bin/env bash
# Show what the host has, what Docker is allocated, what is free, and how to change it permanently.
# Read-only: never starts or stops anything.
set -u

# Rough needs for the act: tasks (runner image + python/uv install)
REC_CPU=2 REC_MEM_GB=4 REC_DISK_GB=30

gb() { awk -v b="$1" 'BEGIN{printf "%.1f", b/1073741824}'; }

echo "== Host =="
case "$(uname -s)" in
  Darwin)
    h_cpu="$(sysctl -n hw.ncpu)"
    h_mem="$(sysctl -n hw.memsize)"
    page="$(vm_stat | sed -n 's/.*page size of \([0-9]*\) bytes.*/\1/p')"
    free_pages="$(vm_stat | awk '/Pages free|Pages inactive|Pages speculative/ {gsub("\\.","",$NF); s+=$NF} END{print s}')"
    h_free=$((free_pages * page)) ;;
  *)
    h_cpu="$(nproc)"
    h_mem="$(awk '/MemTotal/ {print $2*1024}' /proc/meminfo)"
    h_free="$(awk '/MemAvailable/ {print $2*1024}' /proc/meminfo)" ;;
esac
echo "CPU cores:  $h_cpu"
echo "Memory:     $(gb "$h_mem") GB total, ~$(gb "$h_free") GB free/reclaimable"
echo "Disk (/):   $(df -h / | awk 'NR==2 {print $2" total, "$4" free"}')"

runtime=none
if command -v colima >/dev/null 2>&1; then runtime=colima
elif [ "$(uname -s)" = Darwin ] && [ -d /Applications/Docker.app ]; then runtime=desktop
elif command -v docker >/dev/null 2>&1; then runtime=native; fi

echo
echo "== Docker runtime: $runtime =="
if ! command -v docker >/dev/null 2>&1; then echo "Docker CLI not installed. Run: mise run install"; exit 0; fi

d_cpu="" d_mem="" d_disk=""
if [ "$runtime" = colima ]; then
  line="$(colima list --json 2>/dev/null | head -1)"
  if [ -n "$line" ]; then
    status="$(echo "$line" | sed -n 's/.*"status":"\([^"]*\)".*/\1/p')"
    d_cpu="$(echo "$line" | sed -n 's/.*"cpus":\([0-9]*\).*/\1/p')"
    d_mem="$(echo "$line" | sed -n 's/.*"memory":\([0-9]*\).*/\1/p')"
    d_disk="$(echo "$line" | sed -n 's/.*"disk":\([0-9]*\).*/\1/p')"
    echo "Colima VM status: $status (allocated: ${d_cpu} CPU, $(gb "$d_mem") GB RAM, $(gb "$d_disk") GB disk)"
  fi
fi

if docker info >/dev/null 2>&1; then
  i_cpu="$(docker info --format '{{.NCPU}}')"; i_mem="$(docker info --format '{{.MemTotal}}')"
  d_cpu="${d_cpu:-$i_cpu}"; d_mem="${d_mem:-$i_mem}"
  echo "Docker daemon: RUNNING (sees ${i_cpu} CPU, $(gb "$i_mem") GB RAM)"
  echo
  echo "== Allocated vs host =="
  echo "CPU:    ${d_cpu} of ${h_cpu} cores ($((d_cpu * 100 / h_cpu))% of host)"
  echo "Memory: $(gb "$d_mem") GB of $(gb "$h_mem") GB ($((d_mem * 100 / h_mem))% of host)"
  [ -n "$d_disk" ] && echo "Disk:   $(gb "$d_disk") GB virtual disk allowed (sparse; real usage below)"
  echo
  echo "== Docker disk usage =="
  docker system df
  echo
  echo "== Running containers (live usage) =="
  if [ -n "$(docker ps -q)" ]; then
    docker stats --no-stream --format 'table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.MemPerc}}'
  else
    echo "none"
  fi
  free_in_vm="$(docker run --rm --pull=never alpine df -k / 2>/dev/null | awk 'NR==2 {print $4*1024}')"
  [ -n "${free_in_vm:-}" ] && { echo; echo "Free disk inside the Docker VM: $(gb "$free_in_vm") GB"; }
else
  echo "Docker daemon: NOT RUNNING (start it: mise run docker:start). Showing configured values only."
  if [ -z "$d_cpu" ]; then echo "No allocation info available while Docker is stopped."; fi
fi

echo
echo "== Verdict (recommended for act: tasks: ${REC_CPU}+ CPU, ${REC_MEM_GB}+ GB RAM, ${REC_DISK_GB}+ GB disk) =="
ok=1
if [ -n "$d_cpu" ] && [ "$d_cpu" -lt "$REC_CPU" ]; then echo "⚠️  CPU ${d_cpu} < ${REC_CPU}"; ok=0; fi
if [ -n "$d_mem" ] && [ "$(awk -v b="$d_mem" -v r="$REC_MEM_GB" 'BEGIN{print (b/1073741824 < r)}')" = 1 ]; then echo "⚠️  Memory $(gb "$d_mem") GB < ${REC_MEM_GB} GB"; ok=0; fi
if [ -n "$d_disk" ] && [ "$(awk -v b="$d_disk" -v r="$REC_DISK_GB" 'BEGIN{print (b/1073741824 < r)}')" = 1 ]; then echo "⚠️  Disk $(gb "$d_disk") GB < ${REC_DISK_GB} GB"; ok=0; fi
[ "$ok" = 1 ] && echo "✅ Allocation looks sufficient"

echo
echo "== How to change it permanently =="
case "$runtime" in
  colima)
    cat <<'T'
Colima keeps its settings in ~/.colima/default/colima.yaml (cpu, memory in GB, disk in GB).
Persistent change (choose one):
  1. Edit the file:        colima start --edit        (opens colima.yaml; saves and applies on start)
     or edit directly:     $EDITOR ~/.colima/default/colima.yaml   then: colima stop && colima start
  2. One-off flags that are also saved to the config:
                           colima stop && colima start --cpu 4 --memory 8 --disk 100
  3. Defaults for NEW instances: colima template   (edits ~/.colima/_templates/default.yaml)
Notes: CPU/memory changes need a restart (docker:stop then docker:start). Disk can only be grown,
never shrunk. Keep memory below ~half of host RAM so macOS stays responsive.
T
    ;;
  desktop)
    cat <<'T'
Docker Desktop: Settings -> Resources -> Advanced (CPUs, Memory, Swap, Disk image size) -> Apply & restart.
These are stored in ~/Library/Group Containers/group.com.docker/settings-store.json (cpus, memoryMiB, diskSizeMiB),
so editing that file while Docker is quit is also persistent. Disk image size can only be increased.
T
    ;;
  native)
    cat <<'T'
Native Docker on Linux uses the whole host; limit per container with --cpus/--memory, or per daemon via
/etc/docker/daemon.json and systemd slices (e.g. `systemctl set-property docker.service MemoryMax=8G CPUQuota=400%`).
T
    ;;
  *) echo "No runtime detected; run: mise run install" ;;
esac
