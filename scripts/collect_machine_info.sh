#!/bin/bash
# collect_machine_info.sh - Collect detailed hardware and software information

# Set output file
OUTPUT_FILE="machine_info_$(hostname)_$(date +%Y%m%d).txt"

echo "Collecting machine information..."
echo "Output will be saved to: $OUTPUT_FILE"

{
    echo "=========================================="
    echo "Machine Information Report"
    echo "Generated: $(date)"
    echo "Hostname: $(hostname)"
    echo "=========================================="
    echo ""

    # System Information
    echo "=== System Information ==="
    uname -a
    echo ""
    cat /etc/os-release 2>/dev/null || echo "OS release info not available"
    echo ""

    # CPU Information
    echo "=== CPU Information ==="
    lscpu
    echo ""
    cat /proc/cpuinfo | grep "model name" | head -1
    echo "CPU Cores: $(nproc)"
    echo ""

    # Memory Information
    echo "=== Memory Information ==="
    free -h
    echo ""
    vmstat -s
    echo ""

    # GPU Information
    echo "=== GPU Information ==="
    if command -v nvidia-smi &> /dev/null; then
        nvidia-smi
        nvidia-smi --query-gpu=name,memory.total,memory.free,power.draw --format=csv
    else
        echo "No NVIDIA GPU detected"
        # Check for other GPUs
        lspci | grep -i vga || echo "No GPU detected"
    fi
    echo ""

    # Disk Information
    echo "=== Disk Information ==="
    df -h
    echo ""
    lsblk
    echo ""

    # Docker Information
    echo "=== Docker Information ==="
    if command -v docker &> /dev/null; then
        docker --version
        docker info | grep -E "Total Memory|Containers|Images"
        docker ps --format "{{.Names}}" | wc -l | xargs echo "Running containers:"
    else
        echo "Docker not installed"
    fi
    echo ""

    # Network Information
    echo "=== Network Information ==="
    ip a
    echo ""
    ip route
    echo ""
    ping -c 2 google.com &> /dev/null && echo "Internet: Connected" || echo "Internet: Disconnected"
    echo ""

    # Python Environment
    echo "=== Python Environment ==="
    if command -v python3 &> /dev/null; then
        python3 --version
        pip3 --version
    fi
    echo ""

    # CUDA Information
    echo "=== CUDA Information ==="
    if command -v nvcc &> /dev/null; then
        nvcc --version
    else
        echo "CUDA not installed"
    fi
    echo ""

    # Mascarade Specific
    echo "=== Mascarade Specific ==="
    if [ -d "/mascarade" ]; then
        cd /mascarade
        git branch 2>/dev/null || echo "Not a git repo"
        echo "Last commit: $(git log -1 --oneline 2>/dev/null || echo 'Unknown')"
    else
        echo "Mascarade directory not found at /mascarade"
    fi
    echo ""

    echo "=========================================="
    echo "End of Report"
    echo "=========================================="

} > "$OUTPUT_FILE"

echo "Information collected successfully!"
echo "File: $OUTPUT_FILE"
