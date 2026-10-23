from __future__ import annotations
import subprocess
import unittest
from types import SimpleNamespace
from unittest import mock
from hanni.models.resource_manager import snapshot_resources

class ResourceManagerTests(unittest.TestCase):

    @mock.patch('hanni.models.resource_manager.subprocess.run')
    @mock.patch('hanni.models.resource_manager.psutil.cpu_percent', return_value=12.5)
    @mock.patch('hanni.models.resource_manager.psutil.virtual_memory')
    def test_nvidia_and_system_resources(self, memory, cpu, run) -> None:
        memory.return_value = SimpleNamespace(total=32 * 1024 ** 3, used=10 * 1024 ** 3, percent=31.25)
        run.return_value = subprocess.CompletedProcess(args=[], returncode=0, stdout='NVIDIA GeForce RTX 5060 Laptop GPU, 8192, 2048, 42, 66\n', stderr='')
        snap = snapshot_resources(cpu_interval=0)
        self.assertEqual(snap.cpu_percent, 12.5)
        self.assertAlmostEqual(snap.ram_total_gb, 32.0)
        self.assertEqual(len(snap.gpus), 1)
        self.assertEqual(snap.gpus[0].memory_total_mb, 8192)
        self.assertIn('RTX 5060', snap.render_text())

    @mock.patch('hanni.models.resource_manager.subprocess.run')
    @mock.patch('hanni.models.resource_manager.psutil.cpu_percent', return_value=7.0)
    @mock.patch('hanni.models.resource_manager.psutil.virtual_memory')
    def test_amd_vulkan_multi_gpu_fallback(self, memory, cpu, run) -> None:
        memory.return_value = SimpleNamespace(total=32 * 1024 ** 3, used=12 * 1024 ** 3, percent=37.5)

        def side_effect(command, **kwargs):
            if command[0] == 'nvidia-smi':
                raise FileNotFoundError('no nvidia')
            return subprocess.CompletedProcess(args=command, returncode=0, stdout='Available devices:\n  Vulkan0: AMD Radeon RX 9060 XT (16368 MiB, 15000 MiB free)\n  Vulkan1: AMD Radeon RX 6600 XT (8176 MiB, 7600 MiB free)\n  Vulkan2: AMD Radeon(TM) Graphics (15872 MiB, 15000 MiB free)\n', stderr='')
        run.side_effect = side_effect
        snap = snapshot_resources(cpu_interval=0)
        self.assertEqual(len(snap.gpus), 3)
        self.assertEqual(snap.gpus[0].name, 'AMD Radeon RX 9060 XT')
        self.assertEqual(snap.gpus[0].memory_total_mb, 16368)
        self.assertEqual(snap.gpus[0].memory_used_mb, 1368)
        self.assertEqual(snap.gpus[1].memory_total_mb, 8176)
        self.assertIsNone(snap.gpus[0].utilization_percent)
        self.assertIn('llama.cpp', snap.gpu_note or '')

    @mock.patch('hanni.models.resource_manager.subprocess.run', side_effect=FileNotFoundError('missing'))
    @mock.patch('hanni.models.resource_manager.psutil.cpu_percent', return_value=0)
    @mock.patch('hanni.models.resource_manager.psutil.virtual_memory')
    def test_missing_nvidia_smi_is_nonfatal(self, memory, cpu, run) -> None:
        memory.return_value = SimpleNamespace(total=8 * 1024 ** 3, used=2 * 1024 ** 3, percent=25.0)
        snap = snapshot_resources(cpu_interval=0)
        self.assertFalse(snap.gpus)
        self.assertIn('missing', snap.gpu_note or '')
if __name__ == '__main__':
    unittest.main()
