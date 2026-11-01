Class dc.kaggleloader.Installer Extends %RegisteredObject
{

/// Add the installation's Python directory to the current process environment.
ClassMethod Install() As %Status
{
    set cur = $system.Process.GetEnv("PYTHONPATH")
    if cur = "" {
        do $system.Process.SetEnv("PYTHONPATH", "/usr/irissys/mgr/python")
    } elseif $find(cur, "/usr/irissys/mgr/python") = 0 {
        do $system.Process.SetEnv("PYTHONPATH", cur _ ":/usr/irissys/mgr/python")
    }
    quit $$$OK
}

}
