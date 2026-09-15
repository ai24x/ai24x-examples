#!/usr/bin/env python3
"""Compare AI24X managed tier pricing vs official provider rates."""
pricing = {
    "AI24X Managed Tiers": {"flash": 0.35, "pro": 1.05},
    "Official Provider Rates": {
        "GPT-6 Luna": 1.20, "GPT-6 Terra": 12.00, "GPT-6 Sol": 30.00,
        "Claude Opus": 15.00, "Claude Sonnet": 3.00,
        "Gemini Pro": 1.25,
        "DeepSeek Pro (peak)": 3.17, "DeepSeek Flash (peak)": 1.58,
    }
}
print(f"{\"Model\":<25} {\"Rate/M\":<10} {\"AI24X Flash\":<15} {\"AI24X Pro\":<15}")
print("-" * 65)
for model, rate in pricing["Official Provider Rates"].items():
    flash_saving = f"{(1 - 0.35/rate)*100:.0f}%"
    pro_saving = f"{(1 - 1.05/rate)*100:.0f}%"
    print(f"{model:<25} ${rate:<8.2f} ${0.35:<12.2f} ({flash_saving:<4}) ${1.05:<12.2f} ({pro_saving:<4})")
