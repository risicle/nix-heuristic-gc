import os
import tempfile

# this needs to be set before libnixstore_wrapper can be imported,
# before any of pytest's fixtures/tempfile mechanisms can be used.
# the intention here it to prevent any system nix configuration
# leaking in to any libnixstore invocations the tests do.
os.environ["NIX_CONF_DIR"] = tempfile.mkdtemp()  # deliberately empty
os.environ["NIX_USER_CONF_FILES"] = ""
os.environ["NIX_CONFIG"] = f"store = local?root={tempfile.mkdtemp()}"
