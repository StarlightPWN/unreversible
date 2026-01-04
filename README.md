# unreversible
UNBEATABLE Story Mode reverse-engineering/datamining tooling (maybe?)  
currently relies on [AssetRipper](https://github.com/AssetRipper/AssetRipper) output

https://github.com/YarnSpinnerTool/YarnSpinner/blob/v2.0.2/YarnSpinner/yarn_spinner.proto
```sh
$ protoc ./yarn_spinner.proto --python_out=./yarn
```
also we can actually just pull the serialized `FileDescriptor` out of the game code, I just don't feel like it
