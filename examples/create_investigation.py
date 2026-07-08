from packages.python_sdk.opslens import OpsLensClient

client = OpsLensClient()
client.authenticate("ops@opslens.demo")
print(client.create_investigation("SDK-created stockout investigation", "inventory"))
