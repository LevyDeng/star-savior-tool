// A small windowed bridge to the installed Evergreen WebView2 Runtime.
using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Drawing;
using System.IO;
using System.Runtime.InteropServices;
using System.Text;
using System.Web.Script.Serialization;
using System.Windows.Forms;
using Microsoft.Web.WebView2.Core;
using Microsoft.Web.WebView2.WinForms;

internal sealed class WebViewSync : Form
{
    private readonly WebView2 view = new WebView2();
    private readonly Label hint = new Label();
    private readonly Timer timer = new Timer();
    private readonly Stopwatch clock = Stopwatch.StartNew();
    private readonly JavaScriptSerializer json = new JavaScriptSerializer { MaxJsonLength = 10000000 };
    private readonly Dictionary<string, object> config;
    private readonly string job;
    private bool pending;
    private bool stopped;

    [DllImport("user32.dll", EntryPoint = "SetWindowLongPtrW")]
    private static extern IntPtr SetOwner(IntPtr window, int index, IntPtr owner);

    private string Get(string key) { return (string)config[key]; }

    private WebViewSync(string path)
    {
        config = json.Deserialize<Dictionary<string, object>>(File.ReadAllText(path, Encoding.UTF8));
        job = Path.GetDirectoryName(Path.GetFullPath(path));
        Text = Get("title");
        ClientSize = new Size(1000, 720);
        MinimumSize = new Size(640, 480);
        StartPosition = FormStartPosition.CenterScreen;
        Font = new Font("Microsoft YaHei UI", 10);
        BackColor = Color.FromArgb(240, 247, 254);
        hint.Text = Get("hint");
        hint.ForeColor = Color.FromArgb(35, 71, 107);
        hint.Padding = new Padding(14, 10, 14, 6);
        hint.Dock = DockStyle.Top;
        hint.Height = 90;
        var cancel = new Button { Text = Get("cancel"), Dock = DockStyle.Bottom, Height = 40 };
        cancel.Click += delegate { Close(); };
        view.Dock = DockStyle.Fill;
        Controls.Add(view);
        Controls.Add(hint);
        Controls.Add(cancel);
        timer.Interval = 1000;
        timer.Tick += Poll;
        Shown += Start;
        FormClosing += delegate { stopped = true; timer.Stop(); };
    }

    private void Write(string name, object value)
    {
        File.WriteAllText(Path.Combine(job, name), json.Serialize(value), new UTF8Encoding(false));
    }

    private async void Start(object sender, EventArgs args)
    {
        try
        {
            long owner = Convert.ToInt64(config["owner"]);
            if (owner != 0) SetOwner(Handle, -8, new IntPtr(owner));
            // Check before constructing a view; never download or install a runtime silently.
            CoreWebView2Environment.GetAvailableBrowserVersionString();
            var environment = await CoreWebView2Environment.CreateAsync(null, Get("profile"));
            if (stopped) return;
            await view.EnsureCoreWebView2Async(environment);
            if (stopped) return;
            view.CoreWebView2.NewWindowRequested += delegate(object s, CoreWebView2NewWindowRequestedEventArgs e) { e.Handled = true; };
            view.CoreWebView2.PermissionRequested += delegate(object s, CoreWebView2PermissionRequestedEventArgs e) { e.State = CoreWebView2PermissionState.Deny; };
            Write("runtime.json", new { version = environment.BrowserVersionString });
            var uri = new Uri(Get("url"));
            if (uri.Scheme != "https" || uri.Host != "ss.espr.gg") throw new InvalidOperationException("Unexpected sync origin");
            view.Source = uri;
            timer.Start();
        }
        catch (WebView2RuntimeNotFoundException) { Fail("runtime_missing", "WebView2 Runtime is not installed."); }
        catch (Exception error) { if (!stopped) Fail("initialization", error.ToString()); }
    }

    private async void Poll(object sender, EventArgs args)
    {
        if (stopped || pending) return;
        try
        {
            using (var parent = Process.GetProcessById(Convert.ToInt32(config["parent_pid"])))
                if (parent.HasExited) { Close(); return; }
        }
        catch (ArgumentException) { Close(); return; }
        if (clock.Elapsed.TotalSeconds > Convert.ToDouble(config["timeout_seconds"]))
        { Fail("timeout", "Timed out waiting for the complete event payload."); return; }
        pending = true;
        try
        {
            var path = json.Serialize(new Uri(Get("url")).AbsolutePath);
            var script = "(function(){if(location.protocol !== 'https:' || location.hostname !== 'ss.espr.gg' || " +
                "location.pathname.replace(/\\/$/, '') !== " + path + ") return null; return " + Get("script") + ";})()";
            string encoded = await view.ExecuteScriptAsync(script);
            if (stopped || encoded == "null") return;
            string payload = json.Deserialize<string>(encoded);
            if (String.IsNullOrEmpty(payload)) return;
            var raw = json.Deserialize<Dictionary<string, object>>(payload);
            if (!raw.ContainsKey("events") || !raw.ContainsKey("tiers")) return;
            Write("snapshot.json", new Dictionary<string, object> { { "language", Get("language") }, { "data", raw } });
            Environment.ExitCode = 0;
            Close();
        }
        catch (Exception error) { if (!stopped) Fail("extraction", error.ToString()); }
        finally { pending = false; }
    }

    private void Fail(string kind, string detail)
    {
        Write("error.json", new { kind = kind, detail = detail });
        Environment.ExitCode = 1;
        Close();
    }

    [STAThread]
    private static void Main(string[] args)
    {
        Environment.ExitCode = 2;
        if (args.Length != 1) return;
        try
        {
            Application.EnableVisualStyles();
            Application.SetCompatibleTextRenderingDefault(false);
            using (var form = new WebViewSync(args[0])) Application.Run(form);
        }
        catch (Exception error)
        {
            var json = new JavaScriptSerializer();
            File.WriteAllText(Path.Combine(Path.GetDirectoryName(Path.GetFullPath(args[0])), "error.json"),
                json.Serialize(new { kind = "initialization", detail = error.ToString() }), new UTF8Encoding(false));
            Environment.ExitCode = 1;
        }
    }
}
