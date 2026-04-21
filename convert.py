import re

with open('soundverse_new.sql', 'rb') as f:
    raw = f.read()

# 尝试多种编码
for enc in ['utf-16-le', 'utf-16-be', 'utf-8']:
    try:
        content = raw.decode(enc, errors='replace')
        print(f'使用编码: {enc}')
        break
    except:
        continue

# 移除BOM
content = content.replace('\ufeff', '').replace('\ufffe', '')

# 移除null字节
content = content.replace('\x00', '')

# 处理SQL中的特殊字符
# 将单引号转义（SQL中单引号需要用''表示）
# 但不能破坏已经转义的内容

lines = content.split('\n')
result_lines = []
for line in lines:
    # 移除控制字符但保留换行
    clean_line = ''.join(c for c in line if ord(c) >= 32 or c in '\n\r\t')
    if clean_line.strip():
        result_lines.append(clean_line)

content = '\n'.join(result_lines)

with open('soundverse_clean.sql', 'w', encoding='utf-8') as f:
    f.write(content)

print(f'转换完成: {len(content)} 字符, {len(result_lines)} 行')
