from packages.python_sdk.opslens import OpsLensClient

client = OpsLensClient()
client.authenticate("ops@opslens.demo")
print(client.create_scenario("SDK transfer simulation", [{"type": "transfer_inventory", "value": 40}]))
