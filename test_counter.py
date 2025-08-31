from typing import Tuple

class TestCounter:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "count_to": ("INT", {"default": 10, "min": 1, "max": 100}),
            }
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("result",)
    FUNCTION = "count"
    CATEGORY = "Test"
    OUTPUT_NODE = True

    def count(self, count_to: int) -> Tuple[str]:
        print(f"実行: {count_to}")
        return (f"結果: {count_to}",)

# ノードマッピング
NODE_CLASS_MAPPINGS = {
    "TestCounter": TestCounter,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "TestCounter": "Test Counter",
}