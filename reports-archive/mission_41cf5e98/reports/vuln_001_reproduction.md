## Reproduction Steps

### Environment Setup

1. Set up a Mattermost instance (v9.x or later) with default permissions
2. Create three test users:
   - `attacker` - Standard user, NOT a member of target channel
   - `victim` - Standard user to be added without authorization
   - `admin` - System adm...