import logging
import re
import sys
import time
import subprocess
import json

import click

from _ecs_tunnel import EcsTunnel

def getTaskId(cluster, service, aws_region_name):
    command = f"aws ecs list-tasks --cluster {cluster} --service-name {service} --region {aws_region_name}"
    result = subprocess.run(command, shell=True, capture_output=True, text=True)
    try:
        tasks_data = json.loads(result.stdout)
        task_arns = tasks_data.get("taskArns", [])
        if task_arns:
            task_id = (task_arns[0]).split('/')[-1]
            return task_id
        else:
            raise FileNotFoundError("No tasks found")
    except json.JSONDecodeError as e:
        raise FileNotFoundError(f"Error decoding JSON: {e}")
        print(f"Error decoding JSON: {e}")

def getServiceName(cluster, aws_region_name):
    command = f"aws ecs list-services --cluster {cluster}"
    result = subprocess.run(command, shell=True, capture_output=True, text=True)
    try:
        services_data = json.loads(result.stdout)
        service_arns = services_data.get("serviceArns", [])
        if service_arns:
            service_name = (service_arns[0]).split('/')[-1]
            return service_name
        else:
            raise FileNotFoundError("No Services found")
    except json.JSONDecodeError as e:
        raise FileNotFoundError(f"Error decoding JSON: {e}")
        print(f"Error decoding JSON: {e}")

def local_port_forward(ecs_tunnel: EcsTunnel, bind_config: str):
    m = re.match(
        r'(?P<local_port>[\d\-.]+)(:(?P<remote_addr>[\w\-.]+))?:(?P<remote_port>[\d\-.]+)',
        bind_config
    )

    if not m:
        click.echo('Invalid port forward syntax')
        sys.exit(1)

    local_port = int(m.group("local_port"))
    remote_host = m.group('remote_addr')
    remote_port = int(m.group('remote_port'))

    if remote_host:
        ecs_tunnel.remote_port_tunnel(
            local_port=local_port,
            remote_host=remote_host,
            remote_port=remote_port
        )
        click.echo(f'Setup tunnel: 127.0.0.1:{local_port} (Possibly http://127.0.0.1:{local_port}) '
                   f'-> {remote_host}:{remote_port}')
    else:
        ecs_tunnel.local_port_tunnel(
            local_port=local_port,
            remote_port=remote_port
        )
        click.echo(f'Setup tunnel: 127.0.0.1:{local_port} (Possibly http://127.0.0.1:{local_port}) '
                   f'-> {remote_port}')


def dynamic_port_forward(ecs_tunnel: EcsTunnel, port: int):
    ecs_tunnel.http_proxy_port_tunnel(
        local_port=port
    )
    click.echo(f'Setup HTTP Proxy: 127.0.0.1:{port}')


def enable_verbose():
    logging.basicConfig(level=logging.WARNING)
    logging.getLogger('ecs_tunnel').setLevel(level=logging.DEBUG)

@click.command()
@click.option('--cluster', '-c', type=str, required=True, metavar='CLUSTER_NAME')
@click.option('--task', '-t', type=str, required=False, metavar='TASK_ID')
@click.option('--service', '-s', type=str, required=False, metavar='SERVICE_NAME')
@click.option(
    '--container', '-n', type=str, metavar='CONTAINER_NAME',
    help='Container name. Required if task is running more than one container'
)
@click.option(
    '--local',
    '-L', multiple=True, type=str, metavar='LOCAL_PORT:[REMOTE_ADDR:]REMOTE_PORT',
    help='''
Forward a local port.

REMOTE_ADDR is optional. If given, netcat is required on the connected task. Requires Busybox nc, netcat-traditional or NMAP Ncat installed (or any Netcat with support for "-e PROG") on a given ECS task
'''
)
@click.option(
    '--http-proxy',
    '-H', multiple=True, type=int, metavar='PORT',
    help='Setup an HTTP(S) Proxy on given port. Requires NMAP Ncat installed on given ECS task'
)
@click.option(
    '--region', metavar='AWS_REGION', default='eu-west-1',
)
@click.option(
    '--profile', metavar='AWS_PROFILE_NAME',
)
@click.option(
    '--aws-exec', metavar='BIN', help='aws command line executable. (default: "aws")', default='aws'
)
@click.option(
    '--remote-port-netcat-exec', metavar='REMOTE_PORT_NETCAT_EXEC', help='Remote port netcat command line executable. (default: "nc")', default='nc'
)
@click.option('--verbose', is_flag=True, default=False)
def cli(cluster, task, service, container, local, http_proxy, region, profile, aws_exec, remote_port_netcat_exec, verbose):
    action = False
    if verbose:
        enable_verbose()
    if not service:
        service = getServiceName(cluster, region)
    if not task:
        task = getTaskId(cluster, service, region)
    print(f"Starting tunnel for task {task} in service {service} under cluster {cluster} in region {region}") 
    et = EcsTunnel(
        cluster_id=cluster, task_id=task, container_name=container, aws_profile_name=profile, aws_region_name=region,
        aws_cli_exec=aws_exec, remote_port_netcat_exec=remote_port_netcat_exec
    )

    for lp in local:
        local_port_forward(ecs_tunnel=et, bind_config=lp)
        action = True

    for dp in http_proxy:
        dynamic_port_forward(ecs_tunnel=et, port=dp)
        action = True

    if action:
        click.echo('\nPress CTRL-C to stop')
    else:
        click.echo('ERROR: no forwards (-L/-D) given')
        sys.exit(1)

    try:
        while True:
            time.sleep(0.1)
    finally:
        et.close()


if __name__ == '__main__':
    cli()
