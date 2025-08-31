from typing import Tuple
import time

class TestCounter:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "count_to": ("INT", {"default": 10, "min": 1, "max": 100}),
            },
            "optional": {
                "unique_id": ("INT", {"default": 0}),
            }
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("result",)
    FUNCTION = "count"
    CATEGORY = "Test"
    OUTPUT_NODE = True

    def count(self, count_to: int, unique_id=0) -> Tuple[str]:
        # 0の場合は自動でtimestampを生成
        if unique_id == 0:
            unique_id = int(time.time() * 1000)
        
        print(f"実行: {count_to} (unique_id: {unique_id})")
        return (f"結果: {count_to} (ID: {unique_id})",)

# ノードマッピング
NODE_CLASS_MAPPINGS = {
    "TestCounter": TestCounter,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "TestCounter": "Test Counter",
}