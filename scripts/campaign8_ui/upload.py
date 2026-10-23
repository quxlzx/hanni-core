"""Only finite public synthetic bytes may enter the owned original file control."""
import json

def upload_fixture(fixture_id):
    if fixture_id != 'mcp-disabled-config':
        raise ValueError('Unknown synthetic upload fixture; owner files are excluded.')
    content = {'mcpServers': {'Controlled native file integration': {'command': 'campaign8-no-launch.exe', 'args': [], 'env': {}, 'auto_connect': False}}}
    buffer = (json.dumps(content) + '\n').encode('utf8')
    filename = 'campaign8-controlled-disabled-mcp.json'
    if len(buffer) > 256 * 1024 or any((c in filename for c in '/\\:')):
        raise ValueError('Upload must be a bounded synthetic basename.')
    return {'name': filename, 'mimeType': 'application/json', 'buffer': buffer}
