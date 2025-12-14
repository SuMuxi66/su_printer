import yaml
import os

# 要检查的YAML文件列表
yaml_files = [
    'tools/print_text.yaml',
    'tools/print_url.yaml',
    'tools/print_status.yaml',
    'tools/print_queue.yaml',
    'tools/doc_to_pdf.yaml',
    'provider/su_printer.yaml',
    'manifest.yaml'
]

# 检查每个YAML文件
for file_path in yaml_files:
    if os.path.exists(file_path):
        try:
            with open(file_path, 'r') as file:
                yaml.safe_load(file)
            print(f"✅ {file_path}: Valid YAML")
        except yaml.YAMLError as e:
            print(f"❌ {file_path}: Invalid YAML - {e}")
        except Exception as e:
            print(f"❌ {file_path}: Error - {e}")
    else:
        print(f"⚠️  {file_path}: File not found")
