# iRacing Credentials Setup

This bot uses encrypted credential storage for iRacing integration to avoid storing plaintext passwords.

## Prerequisites

1. **Enable Legacy Authentication in iRacing**
   - Log into [iRacing.com](https://www.iracing.com)
   - Go to **Account Settings → Security**
   - Enable **"Legacy Read Only Authentication"**
   - See: https://forums.iracing.com/discussion/22109

## Setup Process

### Step 1: Rebuild Docker Container (if needed)

The encryption library needs to be installed first:

```bash
cd /mnt/e/discord-bot
docker-compose build bot
```

### Step 2: Run the Encryption Script

```bash
docker-compose run --rm bot python encrypt_credentials.py
```

You will be prompted to enter:
- **iRacing Email**: Your iRacing account email
- **iRacing Password**: Your iRacing account password

The script will:
1. Generate an encryption key (or use existing one)
2. Encrypt your credentials
3. Save them to `/app/.iracing_credentials`
4. Set file permissions to 600 (owner read/write only)

### Step 3: Restart the Bot

```bash
docker-compose up -d bot
```

The bot will now use your encrypted credentials automatically.

## How It Works

1. **Encryption Key**: A unique Fernet encryption key is generated and stored in `/app/.encryption_key`
2. **Encrypted Credentials**: Your email and password are encrypted and stored in `/app/.iracing_credentials`
3. **Runtime Decryption**: The bot decrypts credentials in memory when it starts
4. **File Security**: Both files have 600 permissions (only the container user can read/write)

## Security Notes

✅ **Secure**:
- Credentials are encrypted using Fernet (symmetric encryption)
- Files have restricted permissions (600)
- Credential files are excluded from git (`.gitignore`)
- Plaintext credentials never touch disk

⚠️ **Important**:
- DO NOT commit `.encryption_key` or `.iracing_credentials` to version control
- DO NOT share your encryption key
- Both files are mounted via Docker volume from `./bot/` directory
- If you lose the encryption key, you'll need to re-run the setup

## Removing Credentials

To remove iRacing integration:

```bash
docker-compose run --rm bot python -c "from credential_manager import CredentialManager; CredentialManager().remove_credentials()"
```

Or manually delete:
```bash
rm bot/.encryption_key bot/.iracing_credentials
```

## Verifying Setup

Check bot logs after restart:

```bash
docker-compose logs --tail=30 bot | grep iRacing
```

You should see:
```
✅ iRacing integration enabled (using encrypted credentials)
```

## Troubleshooting

**Error: "No encrypted credentials found"**
- Run the encryption script (Step 2 above)

**Error: "Error decrypting credentials"**
- The encryption key may be corrupted
- Remove both files and re-run the encryption script

**Error: "iRacing authentication failed"**
- Verify Legacy Authentication is enabled in your iRacing account
- Re-run the encryption script to update credentials
- Check your email/password are correct

## File Locations

Inside the Docker container:
- `/app/.encryption_key` - Encryption key
- `/app/.iracing_credentials` - Encrypted credentials

On your host machine:
- `e:\discord-bot\bot\.encryption_key`
- `e:\discord-bot\bot\.iracing_credentials`
