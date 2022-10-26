## Development

1. Clone the repository:
    ```shell
    git clone https://github.com/mgax/minivirt
    cd minivirt
    ```

1. Create a virtualenv so you don't interfere with gobally-installed packages:
    ```shell
    python3 -m venv .venv
    source .venv/bin/activate
    ```

1. Install the repo in edit mode and development dependencies:
    ```shell
    pip install -e '.[devel]'
    ```

1. Run the test suite:
    ```shell
    pytest
    pytest --runslow  # if you're not in a hurry
    ```

### Python API

_Minivirt_ is written in Python and offers a straightforward API:

```python
from minivirt.cli import db

alpine = db.get_image('alpine')
myvm = VM.create(db, 'myvm', image=alpine, memory=512)
with myvm.run(wait_for_ssh=30):
    print(myvm.ssh('uname -a', capture=True))
```

### GitHub Actions self-hosted runners

Minivirt comes with a server that launches GitHub Actions runners when a workflow job is queued. Each runner is ephemeral and runs in its own VM.

1. Install extra dependencies:
    ```shell
    pip install -e minivirt[githubactions]
    ```

1. Build an actions runner image:
    ```shell
    miv build recipes/alpine-3.15.yaml --tag alpine-3.15 -v
    miv build recipes/ci-alpine.yaml --tag ci-alpine -v
    miv build recipes/githubactions-alpine.yaml --tag githubactions-alpine -v
    ```

1. Run the server. To interact with the GitHub API, it needs a [GitHub PAT][], and runs `git credentials fill` to retrieve it. It uses [ngrok][] to listen for webhook events; to avoid the ngrok session timing out, set a token in the `NGROK_AUTH_TOKEN` environment variable.
    ```shell
    miv -v githubactions serve githubactions-alpine {repo}
    ```

[GitHub PAT]: https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/creating-a-personal-access-token
[ngrok]: https://ngrok.com/
