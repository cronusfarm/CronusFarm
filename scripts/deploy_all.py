import argparse
import subprocess
import sys
import shutil
import os
from pathlib import Path


def run(cmd: list[str], cwd: Path) -> None:
    # Windows 콘솔(cp949 등)에서 한글 로그가 깨져 보이는 문제를 줄이기 위해,
    # PowerShell 스크립트 출력은 가능하면 ASCII 위주로 유지하고,
    # 여기서는 UTF-8 모드로 실행합니다.
    env = dict(**os.environ)
    env.setdefault("PYTHONUTF8", "1")
    p = subprocess.run(cmd, cwd=str(cwd), env=env)
    if p.returncode != 0:
        raise SystemExit(p.returncode)


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]

    ap = argparse.ArgumentParser(
        description="로컬(Windows)에서 Pi로 복사/업코드/Node-RED 배포를 한 번에 실행합니다."
    )
    ap.add_argument(
        "--pi-host",
        default="ida.mango-larch.ts.net",
        help="Pi 호스트(기본: ida.mango-larch.ts.net)",
    )
    ap.add_argument(
        "--pi-user",
        default="dooly",
        help="Pi 사용자(기본: dooly)",
    )
    ap.add_argument(
        "--skip-arduino",
        action="store_true",
        help="Arduino 업로드 생략",
    )
    ap.add_argument(
        "--apply-nodered",
        action="store_true",
        help="Node-RED까지 자동 적용(merged-deploy.json POST)",
    )
    ap.add_argument(
        "--use-split-flows",
        action="store_true",
        help="분할 플로우(mqtt/dashboard/devflow) 병합 모드 사용",
    )
    ap.add_argument(
        "--skip-merge",
        action="store_true",
        help="Node-RED merge 스크립트 실행을 생략(이미 merged-deploy.json이 준비된 경우)",
    )
    ap.add_argument(
        "--no-auto-port",
        action="store_true",
        help="Arduino 업로드 시 포트 자동탐지를 끔(기본은 자동탐지 ON)",
    )
    ap.add_argument(
        "--skip-nginx-deploy",
        action="store_true",
        help="deploy/nginx 동기화·nginx reload 생략",
    )

    args = ap.parse_args()

    # Node-RED 변경을 반영해야 할 때는, 로컬에서 먼저 병합본을 만듭니다.
    if args.apply_nodered and not args.skip_merge:
        merge_cmd = [sys.executable, "scripts/merge_nodered_deploy.py"]
        if args.use_split_flows:
            merge_cmd.append("--use-split")
        run(merge_cmd, cwd=repo_root)

    ps1 = repo_root / "scripts" / "deploy-cronusfarm-pi.ps1"
    if not ps1.exists():
        print(f"파일을 찾지 못했습니다: {ps1}", file=sys.stderr)
        return 2

    ps_exe = shutil.which("pwsh") or shutil.which("powershell") or "powershell"
    ps_cmd = [
        ps_exe,
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(ps1),
        "-PiHostWan",
        args.pi_host,
        "-PiUser",
        args.pi_user,
    ]
    if args.skip_arduino:
        ps_cmd.append("-SkipArduino")
    else:
        # ACM0/ACM1이 자주 바뀌므로 기본은 자동탐지
        if not args.no_auto_port:
            ps_cmd.append("-AutoPort")
    if args.apply_nodered:
        ps_cmd.append("-ApplyNodeRed")
    if args.use_split_flows:
        ps_cmd.append("-UseSplitFlows")
    if args.skip_nginx_deploy:
        ps_cmd.append("-SkipNginxDeploy")

    run(ps_cmd, cwd=repo_root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

