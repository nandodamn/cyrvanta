param(
    [switch]$Apply
)

$ErrorActionPreference = "Stop"
$arguments = @("$PSScriptRoot/reconcile.py")
if ($Apply) {
    $arguments += "--apply"
}
python @arguments
