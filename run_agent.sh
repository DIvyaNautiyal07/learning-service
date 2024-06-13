# Remove previous agent if exists
if test -d learning_agent; then
  echo "Removing previous agent build"
  rm -r learning_agent
fi

# Remove empty directories to avoid wrong hashes
find . -empty -type d -delete

# Ensure hashes are updated
autonomy packages lock

# Fetch the agent
autonomy fetch --local --agent valory/learning_agent

# Replace params with env vars
source .env
python scripts/aea-config-replace.py

# Copy and add the keys and issue certificates
cd learning_agent
cp $PWD/../ethereum_private_key.txt .
autonomy add-key ethereum ethereum_private_key.txt
autonomy issue-certificates

# Run the agent
aea -s run