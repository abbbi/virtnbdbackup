#!/bin/bash
# Can be used to simulate disk images with lots of extents.

# Image file name
IMAGE="test-image.qcow2"
# Image size in KB (300GB converted to KB as an example, adjust if needed)
SIZE_KB=$((300 * 1024 * 1024))
# Block size in KB (64k)
BLOCK_SIZE_KB=64
# Skip size in KB (128k)
SKIP_SIZE_KB=128
# Step size in KB (block + skip = 192k)
STEP_KB=$((BLOCK_SIZE_KB + SKIP_SIZE_KB))
# Starting offset in KB (64k)
START_OFFSET_KB=64
# Write data or zero blocks: default: zero, remove to write data
WRITEOPT="-z"

# Create the qcow2 image if it doesn't exist
# Convert size to bytes for qemu-img
SIZE_BYTES=$((SIZE_KB * 1024))
if [ ! -f "$IMAGE" ]; then
    if ! qemu-img create -f qcow2 "$IMAGE" "$SIZE_BYTES"; then
        echo "Failed to create image"
        exit 1
    fi
fi

# Calculate number of iterations
# Account for starting offset in calculation
ITERATIONS=$(((SIZE_KB - START_OFFSET_KB) / STEP_KB))

echo "Starting write operations..."
echo "Image size: $SIZE_KB KB"
echo "Block size: $BLOCK_SIZE_KB KB"
echo "Skip size: $SKIP_SIZE_KB KB"
echo "Starting offset: $START_OFFSET_KB KB"
echo "Total iterations: $ITERATIONS"

# Counter for progress
count=0

# Loop to write 64k blocks of zeroes with 128k skips, starting at 64k
offset_kb=$START_OFFSET_KB
while [ $offset_kb -lt $SIZE_KB ]; do
    # Write 64k of zeroes at current offset
    if ! qemu-io -c "write ${WRITEOPT} ${offset_kb}k ${BLOCK_SIZE_KB}k" "$IMAGE" > /dev/null 2>&1;  then
        echo "Write failed at offset ${offset_kb}k"
        exit 1
    fi

    # Show progress every 1000 iterations
    if [ $((count % 1000)) -eq 0 ]; then
        echo "Progress: $count/$ITERATIONS (offset: ${offset_kb}k)"
    fi

    # Move to next position
    offset_kb=$((offset_kb + STEP_KB))
    count=$((count + 1))
done

echo "Write operations completed"
echo "Wrote $count blocks of ${BLOCK_SIZE_KB}k zeroes with ${SKIP_SIZE_KB}k skips"
