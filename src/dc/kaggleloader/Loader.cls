Class dc.kaggleloader.Loader Extends %RegisteredObject
{

/// Report whether the loader class is available for container health checks.
ClassMethod Health() As %Status
{
    quit $$$OK
}

/// Download and import a Kaggle dataset, returning the result as JSON.
ClassMethod Load(handle As %String = "", target As %String = "", limit As %Integer = 0, mode As %String = "replace") As %String [ Language = python ]
{
    import json
    from kaggleloader import load_kaggle_to_iris

    result = load_kaggle_to_iris(handle, target, mode, limit)
    return json.dumps(result)
}

/// Download and list dataset files without importing them into tables.
ClassMethod Info(handle As %String = "") As %String [ Language = python ]
{
    import json
    from kaggleloader import get_dataset_info

    result = get_dataset_info(handle)
    return json.dumps(result)
}

}
