"""
禁用 Streamlit 首次启动的 Email 收集提示(onboarding)

参赛项目不需要 streamlit 的邮箱收集提示,通过创建全局 credentials.toml
设 email 为空来跳过。由 run.bat / setup.bat 自动调用,移植到新电脑时
无需手动配置,确保任何机器首次启动都不弹 Email。

同时项目级 .streamlit/config.toml 已设 gatherUsageStats=false 禁用遥测。
"""
import os
import sys


def main():
    home = os.environ.get('USERPROFILE') or os.path.expanduser('~')
    cfg_dir = os.path.join(home, '.streamlit')
    try:
        os.makedirs(cfg_dir, exist_ok=True)
    except OSError as e:
        print(f'[配置] 警告: 无法创建 {cfg_dir}: {e}', file=sys.stderr)
        return

    cred_path = os.path.join(cfg_dir, 'credentials.toml')
    if not os.path.exists(cred_path):
        try:
            with open(cred_path, 'w', encoding='utf-8') as f:
                f.write('[general]\nemail = ""\n')
            print(f'[配置] 已创建 {cred_path} (禁用 Email 提示)')
        except OSError as e:
            print(f'[配置] 警告: 无法写入 {cred_path}: {e}', file=sys.stderr)
    else:
        print(f'[配置] {cred_path} 已存在,跳过')


if __name__ == '__main__':
    main()
