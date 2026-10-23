"""Synthetic cluster identities; no deployment addresses belong in fixtures."""
from dataclasses import replace
from hanni.dashboard.cluster import NODES as DISPLAY_NODES
NODES = tuple((replace(node, lan_ip=f'192.0.2.{10 + index}', tailscale_ip=f'100.64.0.{10 + index}', username='athena' if node.id == 'hanni' else node.id) if not node.maintenance else node for index, node in enumerate(DISPLAY_NODES)))
