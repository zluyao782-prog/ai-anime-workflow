# External Anime API Bridge Node

This ComfyUI custom node calls an external anime-stylization API from a workflow.

For local dry runs, set `api_endpoint` to `mock`. The node will copy the source image to the output path without calling a network service.

Expected real API response format:

```json
{
  "image_base64": "..."
}
```

Install into the cloned ComfyUI checkout:

```bash
./scripts/install_comfyui_custom_node.sh
```

