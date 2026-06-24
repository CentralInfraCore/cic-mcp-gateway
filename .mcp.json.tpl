{
  "mcpServers": {
    "cic-graph": {
      "command": "{{REPO_ROOT}}/p_venv/bin/python",
      "args": [
        "{{REPO_ROOT}}/mcp-server/server.py"
      ],
      "env": {
        "KB_DATA_DIR": "{{REPO_ROOT}}/kb_data/pkl"
      }
    },
    "cic-gateway": {
      "command": "{{REPO_ROOT}}/p_venv/bin/python",
      "args": [
        "{{REPO_ROOT}}/mcp-server/gateway_server.py"
      ],
      "env": {
        "PYTHONPATH": "{{REPO_ROOT}}"
      }
    }
  }
}
