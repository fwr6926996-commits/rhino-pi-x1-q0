# X1 YOLOv5 手工复现说明

适用范围：本文记录的 X1 Ubuntu 22.04.2/rootfs 50、Python 3.10.12、AidLite 2.5.0.284 及板端已有 YOLOv5 资产。以下步骤是从已保存源码与日志整理的手工入口，**该手工入口仅经过静态语法检查**，也不替代历史冻结监督器或正式验收协议。借用板卡上的新模型运行需另行约定范围。

历史脚本见 [DSP 首次请求](../scripts/q0_sample02_target_runner.py)、[CPU 对照](../scripts/q0_sample03_target_runner.py)、[普通账号 DSP 对照](../scripts/q0_sample05_aidlux_target_runner.py)。其旧 run_id 已使用，不可据此追加重跑。

## 1. ThinkBook 终端：选择设备并进入板端

```bash
adb devices -l
export X1_SERIAL='<自己的设备序列号>'
adb -s "$X1_SERIAL" shell
```

后续命令在 X1 shell 执行，文件路径属于板端。先只读记录环境：

```sh
id
cat /etc/os-release
uname -a
python3 --version
command -v timeout
```

DSP 对照使用已存在的 aidlux 普通账号，由设备持有者使用有效凭据在本机终端认证。若还在 ADB uid=2000 会话，可执行 `su -s /bin/sh aidlux`，成功后再用 `id` 核对。本文不包含密码，不重置账号，不要求 sudo 或修改设备权限。

本次成功记录为 uid=1007，含 system(1000) 组。这是本机已观察到的执行身份；其他镜像不能默认复用 uid 或推断只需增加某个组即可成功。

## 2. 选择一条路径并核对源资产

下面只选择一个 `X1_CASE`。默认示例是 TFLite CPU；需要 DSP 时显式改成 `tflite-dsp`。整段属于准备和校验，还没有启动模型。

```sh
X1_CASE=tflite-cpu

case "$X1_CASE" in
  onnx-cpu)
    X1_BASE=/usr/local/share/aidlite/examples/aidlite_onnx
    X1_SCRIPT=onnx_yolov5_multi.py
    X1_DATASET=onnx_yolov5_multi
    X1_MODEL=cutoff_yolov5s_640_sigmoid.onnx
    X1_SCRIPT_SHA=fb7bfc8f50f3d20147d2c8d3e7a75de6659de7545795721cd6afa44d5c7be4cc
    X1_MODEL_SHA=14490b4ea10caaca2ed4158263bda6bfad6e3736ee76b943cee66973f306141b
    X1_ARG=1
    ;;
  tflite-cpu|tflite-dsp)
    X1_BASE=/usr/local/share/aidlite/examples/aidlite_tflite
    X1_SCRIPT=tflite_yolov5_multi.py
    X1_DATASET=tflite_yolov5_multi
    X1_MODEL=cutoff_yolov5s_640_int8.tflite
    X1_SCRIPT_SHA=88ae8564a835f4bd1a6fb01f44c238a48236d8e12391863fc04c0f0f8fb3b126
    X1_MODEL_SHA=3f1eb9278f59f059e1ac84195f40ea98f292f2463c032b58e3100fa6a6b00dfb
    X1_ARG=1
    if [ "$X1_CASE" = tflite-dsp ]; then
      X1_ARG=3
      if [ "$(id -u)" != 1007 ]; then
        printf '%s\n' 'STOP: this recorded DSP path expects aidlux uid=1007.'
        exit 1
      fi
      case " $(id -G) " in
        *" 1000 "*) ;;
        *) printf '%s\n' 'STOP: expected system group 1000 is absent.'; exit 1 ;;
      esac
    fi
    ;;
  *) printf '%s\n' 'STOP: unknown X1_CASE.'; exit 1 ;;
esac

if ! sha256sum -c <<EOF
$X1_SCRIPT_SHA  $X1_BASE/python/$X1_SCRIPT
$X1_MODEL_SHA  $X1_BASE/data/$X1_DATASET/$X1_MODEL
fb4914d123d97c440cd127ef0e98d4bdc68cd88e2683657528928b4a34014e16  $X1_BASE/data/$X1_DATASET/bus.jpg
EOF
then
  printf '%s\n' 'STOP: source assets differ from the recorded experiment.'
  exit 1
fi
```

三项源资产一致还不代表运行环境完全一致。TFLite 的 11 项资产/库身份见[冻结清单](../manifests/dsp_candidate_assets.json)；历史执行由监督器逐项检查，日志还记录实际加载的插件和版本。与本机身份不同的库、模型或镜像应登记为新环境，不用升级或复制库来强行匹配数字。

## 3. 准备独立目录和上下文记录

同一板端 shell 中继续执行。新目录不覆盖厂商样例，也不复用历史实验目录。

```sh
umask 027
X1_RUN=$(mktemp -d /tmp/x1-yolov5-review-XXXXXX) || exit 1
mkdir "$X1_RUN/python" "$X1_RUN/tmp" || exit 1
cp "$X1_BASE/python/$X1_SCRIPT" "$X1_RUN/python/" || exit 1
ln -s "$X1_BASE/data" "$X1_RUN/data" || exit 1

{
  id
  cat /etc/os-release
  uname -a
  python3 --version
  printf 'case=%s\nargument=%s\n' "$X1_CASE" "$X1_ARG"
  printf 'HOME=%s\nSHELL=%s\n' "$HOME" "$SHELL"
  printf 'LD_LIBRARY_PATH=%s\nADSP_LIBRARY_PATH=%s\n' "${LD_LIBRARY_PATH-}" "${ADSP_LIBRARY_PATH-}"
} > "$X1_RUN/context.txt" 2>&1

sha256sum "$X1_RUN/python/$X1_SCRIPT" > "$X1_RUN/copied_script.sha256"
printf 'Result directory: %s\n' "$X1_RUN"
cd "$X1_RUN/python" || exit 1
```

`X1_RUN` 等变量只存在于当前 shell；切换账号或退出后不能假定它们仍存在，应保存上面打印的确切目录。

## 4. 显式启动一次，最长 120 秒

以下才是实际模型运行，会占用设备资源。已有原脚本配置 10 次 invoke，失败可提前结束；不在外层加循环。

```sh
TMPDIR="$X1_RUN/tmp" PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
  timeout --signal=TERM --kill-after=5s 120s \
  python3 -B "./$X1_SCRIPT" "$X1_ARG" \
  > "$X1_RUN/stdout.txt" 2> "$X1_RUN/stderr.txt"
X1_PROCESS_RC=$?
printf '%s\n' "$X1_PROCESS_RC" > "$X1_RUN/process_exit_code.txt"
printf 'Process exit code: %s\nResult directory: %s\n' "$X1_PROCESS_RC" "$X1_RUN"
```

这段手工入口与历史 Python 监督器不同，未新增运行验证。`timeout` 设置 120 秒并在 TERM 后 5 秒仍未退出时使用 KILL；需要提前停止时用 Ctrl+C，随后核对本次进程退出。保留原目录和日志，不自动再次启动，不自动删缓存。

## 5. 读结果，分别判断进程、模型与设备

在当前 shell 中只读查看：

```sh
cat "$X1_RUN/process_exit_code.txt"
cat "$X1_RUN/stderr.txt"
grep -E 'model load|invoke cost time|检测到|result image|StatusCode|htp delegate' "$X1_RUN/stdout.txt"
```

这里使用板端已有的 `grep` 查看日志，不额外安装查看工具。

判读顺序：

1. **进程**：是否超时、被中断或报错；返回 0 只表示进程状态。
2. **模型**：加载成功、编号 0–9 的调用返回齐全，输出图存在且能够打开。原脚本失败也可能返回 0。
3. **设备**：配置、插件、delegate/fallback 日志与硬件 profiling 分别保存。没有逐节点数据时不推断全图硬件归属。
4. **计时**：只统计实际返回的 invoke，保留首个调用，注明 time.time()、调用数和未单独预热。不要把失败进程寿命当作推理延迟。

对照数据见[结果说明](results.md)，详细摘要见[公开证据](../evidence/README.md)；检测图保留本地，不在本仓库分发。日志含设备授权标识，应先保存原件，再另建脱敏版本用于分享；模型、SDK、缓存及样例图的分发条件另外核实。
