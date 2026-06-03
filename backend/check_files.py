import sqlite3

conn = sqlite3.connect('myai_studio.db')
cursor = conn.cursor()

print('=== 文件统计 ===')
print(f'Files 表记录数: {cursor.execute("SELECT COUNT(*) FROM files").fetchone()[0]}')
print(f'Message attachments 表记录数: {cursor.execute("SELECT COUNT(*) FROM message_attachments").fetchone()[0]}')

print('\n=== 最近上传的文件 ===')
for row in cursor.execute('SELECT id, name, type, mime_type, size, created_at FROM files ORDER BY created_at DESC LIMIT 5'):
    print(f'ID: {row[0]}, Name: {row[1]}, Type: {row[2]}, MIME: {row[3]}, Size: {row[4]}, Created: {row[5]}')

print('\n=== 消息附件关系 ===')
for row in cursor.execute('''
    SELECT ma.message_id, ma.file_id, f.name, m.content 
    FROM message_attachments ma 
    JOIN files f ON ma.file_id = f.id 
    JOIN messages m ON ma.message_id = m.id 
    ORDER BY ma.id DESC LIMIT 5
'''):
    print(f'Message: {row[0]}, File: {row[1]}, FileName: {row[2]}, Content preview: {row[3][:50]}...')

conn.close()
