// Standalone verification; no Qt or bundled browser engine is used.
using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Drawing;
using System.IO;
using System.Text;
using System.Web.Script.Serialization;
using System.Windows.Forms;
using Microsoft.Web.WebView2.Core;
using Microsoft.Web.WebView2.WinForms;

internal sealed class WebView2Probe : Form
{
    private readonly WebView2 view = new WebView2();
    private readonly Label status = new Label();
    private readonly Timer timer = new Timer();
    private readonly Stopwatch clock = Stopwatch.StartNew();
    private readonly JavaScriptSerializer json = new JavaScriptSerializer { MaxJsonLength = 10000000 };
    private readonly string directory;
    private readonly string locale;
    private readonly string script;
    private bool pending;
    private bool completed;

    private WebView2Probe(string output, string language, string extractor)
    {
        directory = Path.GetFullPath(output);
        locale = language;
        script = File.ReadAllText(extractor, Encoding.UTF8);
        Directory.CreateDirectory(directory);
        Text = "StarSavior - System WebView2 verification";
        ClientSize = new Size(1000, 720);
        status.Text = "Loading the source with the installed WebView2 Runtime. Complete any site verification manually.";
        status.Dock = DockStyle.Top;
        status.Height = 42;
        view.Dock = DockStyle.Fill;
        Controls.Add(view);
        Controls.Add(status);
        timer.Interval = 1500;
        timer.Tick += Poll;
        Shown += Start;
        FormClosing += delegate { timer.Stop(); };
    }

    private async void Start(object sender, EventArgs args)
    {
        try
        {
            var environment = await CoreWebView2Environment.CreateAsync(null, Path.Combine(directory, "profile"));
            await view.EnsureCoreWebView2Async(environment);
            File.WriteAllText(Path.Combine(directory, "runtime.txt"), environment.BrowserVersionString);
            view.CoreWebView2.NavigationCompleted += delegate(object s, CoreWebView2NavigationCompletedEventArgs e)
            {
                File.AppendAllText(Path.Combine(directory, "navigation.log"),
                    e.IsSuccess + " | " + e.WebErrorStatus + " | " + view.Source + Environment.NewLine);
            };
            view.Source = new Uri("https://ss.espr.gg/" + locale + "/database/journey-events");
            timer.Start();
        }
        catch (Exception error) { Fail(error.ToString()); }
    }

    private async void Poll(object sender, EventArgs args)
    {
        if (pending || completed) return;
        if (clock.Elapsed.TotalSeconds > 120) { Fail("Timed out waiting for the complete public event payload."); return; }
        pending = true;
        try
        {
            var expectedPath = json.Serialize("/" + locale + "/database/journey-events");
            var guarded = "(function(){if(location.protocol !== 'https:' || location.hostname !== 'ss.espr.gg' || " +
                "location.pathname.replace(/\\/$/, '') !== " + expectedPath + ") return null; return " + script + ";})()";
            string encoded = await view.ExecuteScriptAsync(guarded);
            if (encoded == "null" || encoded == "\"\"") return;
            string payload = json.Deserialize<string>(encoded);
            if (String.IsNullOrEmpty(payload)) return;
            var raw = json.Deserialize<Dictionary<string, object>>(payload);
            if (!raw.ContainsKey("events") || !raw.ContainsKey("tiers")) return;
            var wrapper = new Dictionary<string, object> { { "language", locale }, { "data", raw } };
            File.WriteAllText(Path.Combine(directory, "snapshot.json"), json.Serialize(wrapper), new UTF8Encoding(false));
            File.WriteAllText(Path.Combine(directory, "report.json"), json.Serialize(new {
                ok = true, runtime = view.CoreWebView2.Environment.BrowserVersionString,
                milliseconds = clock.ElapsedMilliseconds,
                browserProcessId = view.CoreWebView2.BrowserProcessId
            }), new UTF8Encoding(false));
            completed = true;
            Environment.ExitCode = 0;
            timer.Stop();
            Close();
        }
        catch (Exception error) { Fail(error.ToString()); }
        finally { pending = false; }
    }

    private void Fail(string error)
    {
        completed = true;
        timer.Stop();
        File.WriteAllText(Path.Combine(directory, "error.txt"), error, Encoding.UTF8);
        Environment.ExitCode = 1;
        Close();
    }

    [STAThread]
    private static void Main(string[] args)
    {
        if (args.Length != 3) { Environment.ExitCode = 2; return; }
        Application.EnableVisualStyles();
        Application.SetCompatibleTextRenderingDefault(false);
        using (var form = new WebView2Probe(args[0], args[1], args[2])) Application.Run(form);
    }
}
