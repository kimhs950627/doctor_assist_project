---
name: linux_github_git
version: 1.0
language: ko
summary: Linux shell 우선 방식으로 GitHub repository를 안전하게 clone, pull, file download, commit, push하는 재사용 Skill.
---

# Linux GitHub Git Skill

## 목적

Linux shell 환경에서 GitHub repository 및 특정 파일을 확보하고, 수정한 파일을 안전하게 commit/push함.

기본 원칙:

- **저장소가 로컬에 없으면 Linux shell 명령으로 clone을 우선 수행함.** Python `subprocess`는 shell 직접 실행이 불가한 환경에서만 대안으로 사용함.
- `main`을 기본 branch로 사용함.
- 실행 전 Git identity 설정함.
- PAT는 명령 출력, commit, source file, remote 영구 설정에 남기지 않음.
- 인증 remote는 clone/push 순간에만 사용하고, 성공·실패와 무관하게 public remote URL로 복원함.
- token을 `print`, `echo`, exception, 로그에 포함하지 않음.
- `git push` 전 변경 파일, branch, diff를 확인함.
- push 후 commit SHA, branch, 변경 파일만 간결히 보고함.

## 입력

```text
owner/repository: GitHub owner/repository
branch: 기본 main
local_dir: clone할 local 경로
PAT: 실행 환경의 secret 또는 사용자 제공 secret
file_path: 선택. raw 파일 다운로드 또는 sparse checkout 대상 경로
commit_message: 수정 후 push할 때 필요
```

## 보안 규칙

1. PAT 전체 문자열을 사용자 응답, markdown, shell 출력, git remote -v 출력에 절대 표시하지 않음.
2. shell history 노출 가능성이 있으므로 CLI command line 직접 token 삽입은 최소화함.
3. 가능하면 `GITHUB_PAT`, `GH_TOKEN`, secret manager, credential helper를 사용함.
4. token이 포함된 원격 URL을 잠시 써야 하면, `subprocess.run(..., capture_output=True)`로 출력 캡처하고 즉시 public URL로 원복함.
5. 오류 메시지를 반환할 때도 token 문자열을 `[REDACTED]` 처리함.
6. PAT를 repository file, `.git/config`, `.env`, notebook output에 저장하지 않음.
7. token이 대화에 이미 노출되었으면 GitHub에서 즉시 revoke하고 새 token을 발급하는 것을 권고함.

## 사전 점검

```bash
command -v git
git --version
git config --global user.name
git config --global user.email
```

identity가 없거나 사용자 지정값이 필요하면:

```bash
git config --global user.name "kimhs950627"
git config --global user.email "kimhs950627@knou.ac.kr"
```

현재 저장소 확인:

```bash
pwd
git rev-parse --show-toplevel
git branch --show-current
git status --short
git remote get-url origin
```

## Clone workflow

### 실행 우선순위

```text
1. Linux shell/bash 직접 실행
2. shell 실행 래퍼가 제공하는 terminal tool
3. Python subprocess는 최후 대안
```

로컬 저장소 부재는 오류가 아니라 clone 조건임. 먼저 경로를 점검한 뒤, 없으면 shell에서 `git clone` 수행함.

### Repository가 없는 경우: Linux shell 우선

`GITHUB_PAT`는 shell session의 secret 환경변수로 주입되어 있다고 가정함. 명령 출력에는 token이 나타나지 않게 `set +x`를 먼저 실행함.

```bash
set +x
REPO_DIR="$HOME/REPOSITORY"
OWNER_REPO="OWNER/REPOSITORY"
BRANCH="main"
PUBLIC_URL="https://github.com/${OWNER_REPO}.git"
AUTH_URL="https://x-access-token:${GITHUB_PAT}@github.com/${OWNER_REPO}.git"

mkdir -p "$(dirname "$REPO_DIR")"
if [ ! -e "$REPO_DIR" ]; then
  git clone --branch "$BRANCH" --single-branch "$AUTH_URL" "$REPO_DIR"
  CLONE_STATUS=$?
  git -C "$REPO_DIR" remote set-url origin "$PUBLIC_URL" 2>/dev/null || true
  [ "$CLONE_STATUS" -eq 0 ] || exit "$CLONE_STATUS"
elif [ -d "$REPO_DIR/.git" ]; then
  git -C "$REPO_DIR" pull --ff-only origin "$BRANCH"
else
  printf '%s\n' "Target path exists but is not a Git repository" >&2
  exit 1
fi
unset AUTH_URL
```

필수 사항:

- `set -x` 사용 금지. token이 command trace에 노출될 수 있음.
- clone 성공 뒤 즉시 `origin`을 PAT 없는 `PUBLIC_URL`로 복원함.
- clone 실패 후에도 `.git`이 생성됐을 수 있으므로 public remote 복원을 시도함.
- remote URL 확인은 `git remote get-url origin`으로 하되, 인증 URL일 가능성이 있으면 사용자-facing output에 그대로 출력하지 않음.

### 이미 clone된 경우

작업 트리가 깨끗한지 먼저 확인한 뒤 fast-forward pull만 수행함.

```bash
REPO_DIR="$HOME/REPOSITORY"
BRANCH="main"

git -C "$REPO_DIR" status --short
if [ -n "$(git -C "$REPO_DIR" status --porcelain)" ]; then
  printf '%s\n' "Working tree is not clean; do not pull automatically" >&2
  exit 1
fi
git -C "$REPO_DIR" fetch origin "$BRANCH"
git -C "$REPO_DIR" pull --ff-only origin "$BRANCH"
```

`pull --ff-only` 실패 시 merge/rebase를 자동으로 강행하지 않음. 원격 변경·로컬 branch·충돌을 확인한 뒤 사용자 판단을 받음.

### Python subprocess fallback

Linux shell tool을 사용할 수 없는 경우에만 아래 방식을 사용함. 실행 결과의 stdout/stderr를 캡처하고 token을 절대 출력하지 않음.

```python
import os
import subprocess
from pathlib import Path

owner_repo = "OWNER/REPOSITORY"
branch = "main"
local_dir = Path.home() / "REPOSITORY"
pat = os.environ["GITHUB_PAT"]
auth_url = f"https://x-access-token:{pat}@github.com/{owner_repo}.git"
public_url = f"https://github.com/{owner_repo}.git"

try:
    subprocess.run(["git", "clone", "--branch", branch, "--single-branch", auth_url, str(local_dir)],
                   check=True, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
finally:
    if (local_dir / ".git").exists():
        subprocess.run(["git", "-C", str(local_dir), "remote", "set-url", "origin", public_url],
                       check=False, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
```

## 특정 파일만 받기

### 이미 clone된 repository

```bash
cd /path/to/repository
git fetch origin main
git checkout origin/main -- path/to/file
```

이 명령은 working tree 파일을 변경할 수 있으므로 현재 파일이 수정되었는지 먼저 확인함.

```bash
git status --short -- path/to/file
```

### Sparse checkout

큰 repository에서 특정 directory만 필요할 때 사용함.

```bash
git clone --filter=blob:none --no-checkout https://github.com/OWNER/REPOSITORY.git repo
cd repo
git sparse-checkout init --cone
git sparse-checkout set board_exam
```

private repository이면 clone URL에 일시 인증을 적용하고 직후 public remote로 원복함.

### Raw file download

version-controlled checkout이 불필요할 때만 사용함.

```python
import os
import urllib.request
from pathlib import Path

owner_repo = "OWNER/REPOSITORY"
branch = "main"
file_path = "path/to/file"
pat = os.environ["GITHUB_PAT"]
url = f"https://raw.githubusercontent.com/{owner_repo}/{branch}/{file_path}"
request = urllib.request.Request(url, headers={"Authorization": f"Bearer {pat}"})
with urllib.request.urlopen(request) as response:
    Path(file_path).name and Path("downloaded_file").write_bytes(response.read())
```

다운로드 후 SHA256과 파일 크기를 확인함.

```bash
sha256sum downloaded_file
file downloaded_file
```

## 수정 및 commit workflow

1. 최신 `main` 반영.
2. 파일 수정.
3. 변경 범위 검토.
4. stage.
5. commit.
6. authenticated push.
7. public remote 복원.
8. SHA와 변경 파일 확인.

```bash
cd /path/to/repository
git pull --ff-only origin main
git status --short
git diff --check
git diff -- path/to/changed_file
git add path/to/changed_file
git diff --cached --check
git diff --cached --stat
git commit -m "feat: concise imperative message"
```

## Push workflow

Linux shell push를 우선 사용함. `origin`은 공개 URL로 유지하고, push 직전에만 인증 URL을 사용한 뒤 shell trap으로 반드시 원복함. Python subprocess는 shell 실행이 불가한 경우에만 사용함.


### Linux shell push 우선

```bash
set +x
REPO_DIR="$HOME/REPOSITORY"
OWNER_REPO="OWNER/REPOSITORY"
BRANCH="main"
PUBLIC_URL="https://github.com/${OWNER_REPO}.git"
AUTH_URL="https://x-access-token:${GITHUB_PAT}@github.com/${OWNER_REPO}.git"

restore_remote() {
  git -C "$REPO_DIR" remote set-url origin "$PUBLIC_URL" >/dev/null 2>&1 || true
  unset AUTH_URL
}
trap restore_remote EXIT INT TERM

git -C "$REPO_DIR" remote set-url origin "$AUTH_URL"
git -C "$REPO_DIR" push origin "$BRANCH"
```

`trap`은 push 성공, 실패, interrupt 모두에서 remote 복원을 보장함. `git push` 결과를 사용자에게 표시할 때 credential 문자열이 포함된 raw log는 출력하지 않음.

```python
import os
import subprocess

repo = "/path/to/repository"
owner_repo = "OWNER/REPOSITORY"
branch = "main"
pat = os.environ["GITHUB_PAT"]
auth_url = f"https://x-access-token:{pat}@github.com/{owner_repo}.git"
public_url = f"https://github.com/{owner_repo}.git"

try:
    subprocess.run(["git", "remote", "set-url", "origin", auth_url], cwd=repo, check=True,
                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    pushed = subprocess.run(["git", "push", "origin", branch], cwd=repo, text=True,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if pushed.returncode != 0:
        raise RuntimeError("git push failed; inspect redacted stderr only")
finally:
    subprocess.run(["git", "remote", "set-url", "origin", public_url], cwd=repo, check=False,
                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
```

일시적 network/403 오류는 1~2회 지연 재시도 가능함. 인증 실패가 계속되면 token scope, repository access, branch protection을 확인함.

```python
import time
for attempt in range(2):
    result = subprocess.run(["git", "push", "origin", branch], cwd=repo, text=True,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode == 0:
        break
    time.sleep(3 * (attempt + 1))
else:
    raise RuntimeError("git push failed after retry")
```

## 완료 검증

```bash
git status --short
git branch --show-current
git rev-parse HEAD
git show --stat --oneline -1
git remote get-url origin
```

성공 조건:

- working tree clean
- branch가 예상 branch
- `HEAD`가 새 commit
- origin이 PAT 없는 public URL
- `git push` exit code 0

## 오류 대응

| 오류 | 확인 | 처리 |
|---|---|---|
| `Authentication failed` | token 유효성, fine-grained token repository 권한, Contents read/write | token 교체 또는 scope 수정 |
| `403` | repository 권한, branch protection, SSO 승인 | 권한/보호 규칙 확인, 필요 시 PR branch 사용 |
| `non-fast-forward` | 원격 선행 commit 여부 | `fetch`, `pull --ff-only`; 충돌 시 자동 강행하지 않음 |
| `would overwrite local changes` | `git status --short` | diff 백업 또는 사용자 판단 후 stash/commit |
| `pathspec` 오류 | 정확한 repository-relative path | `git ls-files`, `find`로 경로 확인 |
| clone는 됐지만 file 없음 | branch 및 sparse pattern | `git branch -a`, `git sparse-checkout list` 확인 |

## 금지

- `git push --force`를 기본값으로 사용하지 않음.
- 사용자 확인 없이 `reset --hard`, `clean -fd`, `stash drop`, history rewrite 하지 않음.
- PAT를 응답이나 committed document에 기록하지 않음.
- push 실패 시 원인을 숨기거나 성공으로 보고하지 않음.
- private repository URL이나 token 포함 URL을 사용자-facing log에 출력하지 않음.

## 완료 보고 형식

```text
Git 작업 완료함.

- 작업: clone / pull / 파일 다운로드 / commit + push
- 저장소: owner/repository
- local path: /path/to/repository
- branch: main
- commit: <full SHA 또는 short SHA>
- 변경 파일: <목록>
- remote: PAT 없는 공개 URL로 복원함
- 검증: PASS
```

실패 시:

```text
Git 작업 실패함.

- 단계: clone / pull / commit / push
- 원인: token을 제거한 핵심 오류만 표시
- repository 상태: branch, dirty/clean 여부
- 안전 조치: remote public URL 복원 여부
- 다음 확인: 권한 / token scope / 충돌 중 필요한 한 가지
```
