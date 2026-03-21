#!/bin/bash
# collect_all_machines.sh - Collect info from all machines in the cluster

# Configuration
MACHINES=(
    "root@192.168.0.119:vm_119"
    "clems@192.168.0.120:clems_120"
    "kxkm@kxkm-ai:kxkm_ai"
    "cils@100.126.225.111:cils_111"
)

OUTPUT_DIR="machine_inventory"
mkdir -p "$OUTPUT_DIR"

echo "Starting machine information collection..."
echo "Output directory: $OUTPUT_DIR"
echo ""

# Collect from each machine
for machine in "${MACHINES[@]}"; do
    IFS=':' read -r user_host alias <<< "$machine"
    
    echo "=== Collecting from $user_host ($alias) ==="
    
    # Copy script and execute
    scp scripts/collect_machine_info.sh "$user_host":~/ || {
        echo "Failed to copy script to $user_host"
        continue
    }
    
    # Execute remotely
    ssh "$user_host" "bash ~/collect_machine_info.sh" || {
        echo "Failed to execute on $user_host"
        continue
    }
    
    # Retrieve results
    scp "$user_host":~/machine_info_*.txt "$OUTPUT_DIR/$alias.txt" || {
        echo "Failed to retrieve results from $user_host"
        continue
    }
    
    # Cleanup remote
    ssh "$user_host" "rm -f ~/machine_info_*.txt"
    
    echo "Completed: $alias"
    echo ""
done

echo "All collections completed!"
echo ""
echo "Generating summary..."

# Generate summary
python3 << 'EOF'
import os
import re

output_dir = "machine_inventory"
summary_file = os.path.join(output_dir, "SUMMARY.md")

with open(summary_file, 'w') as f:
    f.write("# Machine Inventory Summary\n\n")
    f.write(f"Generated: {__import__('datetime').datetime.now()}\n\n")

    # Process each machine file
    for filename in sorted(os.listdir(output_dir)):
        if not filename.endswith('.txt'):
            continue

        filepath = os.path.join(output_dir, filename)
        alias = filename.replace('.txt', '')

        f.write(f"## {alias}\n\n")

        with open(filepath, 'r') as machine_file:
            content = machine_file.read()

            # Extract key information
            hostname = re.search(r'Hostname: (\S+)', content)
            cpu_cores = re.search(r'CPU Cores: (\d+)', content)
            total_mem = re.search(r'Mem:\s+(\d+G)', content)
            gpu_mem = re.search(r'Memory.*Total\s+:\s+(\d+\s+[MG]iB)', content)
            docker_mem = re.search(r'Total Memory\s+:\s+(\S+)', content)

            f.write("**Basic Info:**\n")
            if hostname:
                f.write(f"- Hostname: {hostname.group(1)}\n")
            if cpu_cores:
                f.write(f"- CPU Cores: {cpu_cores.group(1)}\n")
            if total_mem:
                f.write(f"- RAM: {total_mem.group(1)}\n")
            if gpu_mem:
                f.write(f"- GPU Memory: {gpu_mem.group(1)}\n")
            if docker_mem:
                f.write(f"- Docker Memory: {docker_mem.group(1)}\n")

            f.write("\n**Full Report:**\n")
            f.write(f"- [View detailed report]({filename})\n")
            f.write("\n")

print(f"Summary generated: {summary_file}")
EOF

echo "Done!"
echo ""
echo "Files generated:"
ls -lh "$OUTPUT_DIR"
