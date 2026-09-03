# ==============================================================================
# Desktop Pet Global Hotkey Helper for Windows (Win + Z Push-to-Talk)
# ==============================================================================

Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;
using System.Windows.Forms;

public class HotKeyHelper : Form {
    [DllImport("user32.dll")]
    public static extern bool RegisterHotKey(IntPtr hWnd, int id, int fsModifiers, int vk);
    [DllImport("user32.dll")]
    public static extern bool UnregisterHotKey(IntPtr hWnd, int id);

    public const int MOD_WIN = 0x0008;
    public const int VK_Z = 0x5A;
    public const int WM_HOTKEY = 0x0312;

    public Action OnHotKey;

    public HotKeyHelper(Action onHotKey) {
        this.OnHotKey = onHotKey;
        RegisterHotKey(this.Handle, 1, MOD_WIN, VK_Z);
    }

    protected override void WndProc(ref Message m) {
        if (m.Msg == WM_HOTKEY && m.WParam.ToInt32() == 1) {
            OnHotKey?.Invoke();
        }
        base.WndProc(ref m);
    }

    protected override void Dispose(bool disposing) {
        UnregisterHotKey(this.Handle, 1);
        base.Dispose(disposing);
    }
}
"@ -ReferencedAssemblies "System.Windows.Forms"

$udpClient = New-Object System.Net.Sockets.UdpClient
$endpoint = New-Object System.Net.IPEndPoint([System.Net.IPAddress]::Parse("127.0.0.1"), 5556)

Write-Host "Desktop Pet Hotkey Helper Active: Press Win + Z to interact." -ForegroundColor Cyan

$action = {
    $bytes = [System.Text.Encoding]::ASCII.GetBytes("voice_action_z")
    $udpClient.Send($bytes, $bytes.Length, $endpoint) | Out-Null
    Write-Host "[Hotkey] Sent voice_action_z trigger" -ForegroundColor Green
}

$form = New-Object HotKeyHelper($action)
[System.Windows.Forms.Application]::Run($form)
