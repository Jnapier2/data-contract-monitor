from pathlib import Path

from data_contract_monitor.demo import write_demo_dataset

if __name__ == "__main__":
    root = Path(__file__).resolve().parent
    write_demo_dataset(root / "data" / "customer_orders_good_generated.csv", valid=True)
    write_demo_dataset(root / "data" / "customer_orders_bad_generated.csv", valid=False)
    print("Generated current-time demo data in examples/data")
