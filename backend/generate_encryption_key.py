"""
生成 API 密钥加密密钥

此脚本生成一个用于加密/解密 API 密钥的密钥。
请将生成的密钥保存到环境变量 API_KEY_ENCRYPTION_KEY 中。

⚠️ 重要提示：
1. 请妥善保管这个密钥，丢失后将无法解密已存储的 API 密钥
2. 所有服务器实例必须使用相同的密钥
3. 修改密钥后，需要重新配置所有 API 密钥
"""

from cryptography.fernet import Fernet

# 生成新的加密密钥
encryption_key = Fernet.generate_key()

print("=" * 80)
print("API 密钥加密密钥生成成功！")
print("=" * 80)
print()
print("请将以下密钥设置到环境变量 API_KEY_ENCRYPTION_KEY:")
print()
print(f"  {encryption_key.decode()}")
print()
print("=" * 80)
print()
print("在 Windows 上设置环境变量（PowerShell）:")
print()
print(f'  $env:API_KEY_ENCRYPTION_KEY="{encryption_key.decode()}"')
print()
print("在 Linux/Mac 上设置环境变量（Bash）:")
print()
print(f'  export API_KEY_ENCRYPTION_KEY="{encryption_key.decode()}"')
print()
print("或者添加到 .env 文件:")
print()
print(f'  API_KEY_ENCRYPTION_KEY="{encryption_key.decode()}"')
print()
print("=" * 80)
print()
print("⚠️ 警告：请妥善保管此密钥，丢失后将无法解密已存储的 API 密钥！")
print()
