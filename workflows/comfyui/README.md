# ComfyUI Workflow Notes

This folder stores ComfyUI workflow payload examples for the AI anime workflow.

The current implementation treats ComfyUI as an orchestrator. The workbench can submit a prompt payload to a running ComfyUI server at `http://127.0.0.1:8188`.

For external anime-stylization, use one of these patterns:

1. Install a custom ComfyUI node that calls the selected anime API.
2. Let the workbench call the anime API directly through `anime_workflow.services.anime_api_adapter`, then register the resulting files in the project.

The example JSON uses a placeholder `ExternalAnimeStylize` node. Replace it with the actual custom node class after choosing the provider.

