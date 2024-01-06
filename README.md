# AWS ECS DB Tunnel
 
## Prerequisites
 - Python 3.8

 - AWS CLI 2.x - https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html
 - AWS Session Manager Plugin -
https://docs.aws.amazon.com/systems-manager/latest/userguide/session-manager-working-with-install-plugin.html
## Usage

Tunnel local port 7432 to port 5432 on a remote host:
```
python3 cli.py -L 6432:<DB_HOST>:5432 -c <CLUSTER_NAME>
```
