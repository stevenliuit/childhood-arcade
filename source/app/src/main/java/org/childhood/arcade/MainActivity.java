package org.childhood.arcade;

import android.app.Activity;
import android.content.Intent;
import android.content.ActivityNotFoundException;
import android.hardware.input.InputManager;
import android.net.Uri;
import android.os.Bundle;
import android.util.AtomicFile;
import android.util.Base64;
import android.view.InputDevice;
import android.view.KeyEvent;
import android.view.MotionEvent;
import android.view.View;
import android.view.WindowManager;
import android.webkit.JavascriptInterface;
import android.webkit.ValueCallback;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceRequest;
import android.webkit.WebResourceResponse;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.Toast;
import android.widget.FrameLayout;
import org.json.JSONArray;
import org.json.JSONObject;
import java.io.*;
import java.util.HashMap;

public class MainActivity extends Activity implements InputManager.InputDeviceListener {
    public static volatile MainActivity instance;
    public static final String DEFAULT_ROOT="/sdcard/ChildhoodArcade";
    public static String externalRoot(android.content.Context c){try{String v=c.getSharedPreferences("deployment",0).getString("external_root",DEFAULT_ROOT);return v==null||v.length()==0?DEFAULT_ROOT:v;}catch(Exception e){return DEFAULT_ROOT;}}
    public static void setExternalRoot(android.content.Context c,String v){try{c.getSharedPreferences("deployment",0).edit().putString("external_root",v).apply();}catch(Exception ignored){}}

    private WebView web;
    private NativeNes nativeNes;
    HallResources resources;
    private ValueCallback<Uri[]> chooser;
    private String pendingBackup;
    private boolean fallbackPackActive;
    private boolean fallbackBackupActive;
    private boolean fallbackFileActive;
    private InputManager inputs;
    private final HashMap<Integer, boolean[]> axes = new HashMap<Integer, boolean[]>();
    private final HashMap<Integer, float[]> sentAxes = new HashMap<Integer, float[]>();
    private final HashMap<Integer, boolean[]> triggers=new HashMap<Integer, boolean[]>();
    private final HashMap<Integer, float[]> rawAxes = new HashMap<Integer, float[]>();
    private volatile JSONObject controllerConfig=new JSONObject();
    private final HashMap<Integer, Integer> players = new HashMap<Integer, Integer>();
    private File storeDir;
    private final Object storeLock = new Object();
    private static final int PICK_FILE=10, EXPORT_FILE=11, PICK_PACK=12;

    @Override public void onCreate(Bundle saved) {
        super.onCreate(saved);
        instance=this;
        if(android.os.Build.VERSION.SDK_INT>=23&&checkSelfPermission(android.Manifest.permission.READ_EXTERNAL_STORAGE)!=android.content.pm.PackageManager.PERMISSION_GRANTED){requestPermissions(new String[]{android.Manifest.permission.READ_EXTERNAL_STORAGE},100);}
        HallUpdates.configureTls(this);
        getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
        hideSystemUI();
        storeDir=new File(getFilesDir(),"store");
        File recovery=new File(getFilesDir(),"store.previous");
        if(!storeDir.exists()&&recovery.exists())recovery.renameTo(storeDir);
        storeDir.mkdirs();
        resources=new HallResources(this);
        WebView.setWebContentsDebuggingEnabled(false);
        getSharedPreferences("deployment",0).edit().putBoolean("page_loaded",false).remove("health").remove("health_at").apply();
        web=new WebView(this);
        WebSettings settings=web.getSettings();
        settings.setJavaScriptEnabled(true);
        settings.setDomStorageEnabled(true);
        settings.setDatabaseEnabled(true);
        settings.setAllowFileAccess(true);
        settings.setAllowContentAccess(true);
        settings.setAllowFileAccessFromFileURLs(false);
        settings.setAllowUniversalAccessFromFileURLs(false);
        settings.setMediaPlaybackRequiresUserGesture(false);
        settings.setTextZoom(100);
        web.setBackgroundColor(0x00000000);
        web.addJavascriptInterface(new Bridge(),"NativeArcade");
        web.setWebViewClient(new WebViewClient(){
            @Override public boolean shouldOverrideUrlLoading(WebView v,String url){return !(url.startsWith("file:///android_asset/")||url.startsWith("https://appassets.androidplatform.net/assets/"));}
            @Override public WebResourceResponse shouldInterceptRequest(WebView v,WebResourceRequest request){
                String address=request.getUrl().toString();
                if(address.startsWith("https://appassets.androidplatform.net/assets/")){
                    String asset=request.getUrl().getPath().substring("/assets/".length());
                    if(asset.contains("..")||asset.startsWith("/"))return new WebResourceResponse("text/plain","UTF-8",new ByteArrayInputStream(new byte[0]));
                    if("catalog.js".equals(asset)){try{String[] plats=new String[]{"nes","arcade","gba","md","sfc"};org.json.JSONArray all=new org.json.JSONArray();for(String p:plats){File gj=new File(new File(externalRoot(MainActivity.this),p),"games.json");if(!gj.isFile())continue;String json=new String(readAll(new FileInputStream(gj),8*1024*1024),"UTF-8");org.json.JSONArray arr=new org.json.JSONArray(json);for(int i=0;i<arr.length();i++){org.json.JSONObject g=arr.getJSONObject(i);g.put("path",p+"/"+g.getString("path"));g.put("art",p+"/"+g.getString("art"));all.put(g);}}java.util.Map<String,String> hdr=new java.util.HashMap<String,String>();hdr.put("Cache-Control","no-store");return new WebResourceResponse("text/javascript","UTF-8",200,"OK",hdr,new ByteArrayInputStream(("window.GAME_CATALOG="+all.toString()+";").getBytes("UTF-8")));}catch(Exception ignored){}}
                    if(asset.endsWith(".png")){File cf=new File(externalRoot(MainActivity.this),asset);if(cf.isFile())try{return new WebResourceResponse("image/png",null,new FileInputStream(cf));}catch(Exception ignored){}}
                    String mime=asset.endsWith(".js")?"text/javascript":asset.endsWith(".css")?"text/css":asset.endsWith(".html")?"text/html":asset.endsWith(".wasm")?"application/wasm":asset.endsWith(".png")?"image/png":asset.endsWith(".ttf")?"font/ttf":"application/octet-stream";
                    try{return new WebResourceResponse(mime,(mime.startsWith("text/")?"UTF-8":null),getAssets().open(asset));}catch(IOException e){return new WebResourceResponse("text/plain","UTF-8",404,"Not Found",null,new ByteArrayInputStream(new byte[0]));}
                }
                String scheme=request.getUrl().getScheme();
                if("http".equals(scheme)||"https".equals(scheme))return new WebResourceResponse("text/plain","UTF-8",new ByteArrayInputStream(new byte[0]));
                return null;
            }
            @Override public void onPageFinished(WebView v,String url){hideSystemUI();if(url.equals("https://appassets.androidplatform.net/assets/index.html"))getSharedPreferences("deployment",0).edit().putBoolean("page_loaded",true).apply();}
        });
        web.setWebChromeClient(new WebChromeClient(){
            @Override public boolean onShowFileChooser(WebView v,ValueCallback<Uri[]> callback,FileChooserParams params){
                if(chooser!=null)chooser.onReceiveValue(null);
                chooser=callback;
                Intent intent=new Intent(Intent.ACTION_OPEN_DOCUMENT);
                intent.addCategory(Intent.CATEGORY_OPENABLE);intent.setType("*/*");
                intent.putExtra(Intent.EXTRA_ALLOW_MULTIPLE,params.getMode()==FileChooserParams.MODE_OPEN_MULTIPLE);
                fallbackFileActive=false;try{startActivityForResult(intent,PICK_FILE);}catch(ActivityNotFoundException e){fallbackFileActive=true;new LegacyBackupPicker(MainActivity.this).start();}
                return true;
            }
        });
        FrameLayout root=new FrameLayout(this);root.setBackgroundColor(0xff100f0c);
        root.addView(web,new FrameLayout.LayoutParams(-1,-1));
        setContentView(root);nativeNes=new NativeNes(this,root);
        web.loadUrl("https://appassets.androidplatform.net/assets/index.html");
        web.post(new Runnable(){public void run(){if(web==null)return;
            web.evaluateJavascript("(function(){var a=window.Arcade;return {title:document.title,ready:!!a,state:a?a.getState():null,catalogCount:window.GAME_CATALOG?window.GAME_CATALOG.length:0,visible:document.visibilityState};})()",new ValueCallback<String>(){public void onReceiveValue(String value){getSharedPreferences("deployment",0).edit().putString("health",value).putLong("health_at",android.os.SystemClock.elapsedRealtime()).apply();}});
            web.postDelayed(this,1000);
        }});
        inputs=(InputManager)getSystemService(INPUT_SERVICE);inputs.registerInputDeviceListener(this,null);
    }
    @Override public void onRequestPermissionsResult(int request,String[] permissions,int[] results){super.onRequestPermissionsResult(request,permissions,results);if(request==LegacyPackPicker.PERMISSION)new LegacyPackPicker(this).permissionResult(results.length>0&&results[0]==android.content.pm.PackageManager.PERMISSION_GRANTED);if(request==LegacyBackupExporter.PERMISSION)new LegacyBackupExporter(this).permissionResult(results.length>0&&results[0]==android.content.pm.PackageManager.PERMISSION_GRANTED);if(request==LegacyBackupPicker.PERMISSION)new LegacyBackupPicker(this).permissionResult(results.length>0&&results[0]==android.content.pm.PackageManager.PERMISSION_GRANTED);}
    void legacyFileFinished(Uri uri){if(chooser!=null){chooser.onReceiveValue(uri==null?null:new Uri[]{uri});chooser=null;}}
    String legacyBackupData(){return pendingBackup;}
    void legacyBackupFinished(boolean ok){pendingBackup=null;js("Arcade.backupResult("+ok+")");if(!ok)Toast.makeText(this,"备份未保存，请检查存储权限和空间",Toast.LENGTH_LONG).show();}
    private void hideSystemUI(){getWindow().getDecorView().setSystemUiVisibility(View.SYSTEM_UI_FLAG_FULLSCREEN|View.SYSTEM_UI_FLAG_HIDE_NAVIGATION|View.SYSTEM_UI_FLAG_IMMERSIVE_STICKY|View.SYSTEM_UI_FLAG_LAYOUT_FULLSCREEN|View.SYSTEM_UI_FLAG_LAYOUT_HIDE_NAVIGATION|View.SYSTEM_UI_FLAG_LAYOUT_STABLE);}
    private void js(final String value){if(web!=null)web.post(new Runnable(){public void run(){if(web!=null)web.evaluateJavascript("if(window.Arcade){"+value+"}",null);}});}
    @Override public void onWindowFocusChanged(boolean focused){super.onWindowFocusChanged(focused);if(focused)hideSystemUI();}
    @Override protected void onPause(){if(nativeNes!=null)nativeNes.pause();super.onPause();js("Arcade.lifecyclePause()");}
    @Override protected void onResume(){super.onResume();if(web!=null)js("Arcade.updateResumed&&Arcade.updateResumed()");}
    @Override protected void onDestroy(){if(nativeNes!=null)nativeNes.close();if(inputs!=null)inputs.unregisterInputDeviceListener(this);if(web!=null){web.removeJavascriptInterface("NativeArcade");web.destroy();web=null;}super.onDestroy();}
    private boolean gamepad(KeyEvent event){return (event.getSource()&InputDevice.SOURCE_GAMEPAD)==InputDevice.SOURCE_GAMEPAD||(event.getSource()&InputDevice.SOURCE_JOYSTICK)==InputDevice.SOURCE_JOYSTICK;}
    private String controllerKey(int id){InputDevice device=InputDevice.getDevice(id);return device==null?"安卓输入设备 "+id:device.getName()+" ["+device.getDescriptor()+"]";}
    private int player(int id){
        Integer existing=players.get(id);if(existing!=null&&(existing!=0||nativeNes==null||!nativeNes.supportsFourPlayers()))return existing;
        int value=!players.containsValue(1)?1:!players.containsValue(2)?2:0;players.put(id,value);
        js("Arcade.nativeRegister("+id+","+value+","+JSONObject.quote(controllerKey(id))+")");return value;
    }
    @Override public boolean dispatchKeyEvent(KeyEvent e){
        int c=e.getKeyCode();
        if(c==KeyEvent.KEYCODE_VOLUME_UP||c==KeyEvent.KEYCODE_VOLUME_DOWN||c==KeyEvent.KEYCODE_VOLUME_MUTE)return super.dispatchKeyEvent(e);
        boolean handle=c==4||c==19||c==20||c==21||c==22||c==23||c==66||c==82||c==96||c==97||c==99||c==100||c==108||c==109||c==110||c==102||c==103||c==104||c==105||c==106||c==107||gamepad(e);
        if(handle&&(e.getAction()==KeyEvent.ACTION_DOWN||e.getAction()==KeyEvent.ACTION_UP)){
            boolean pad=gamepad(e);int p=pad?player(e.getDeviceId()):1;
            // Route all gameplay input through the shared remapping/combination router.
            js("Arcade.nativeKey("+c+","+(e.getAction()==KeyEvent.ACTION_DOWN)+","+e.getDeviceId()+","+gamepad(e)+","+(e.getRepeatCount()>0)+")");return true;
        }
        return super.dispatchKeyEvent(e);
    }
    // WebView consumes joystick motion before Activity.onGenericMotionEvent.
    // Intercept at dispatch so hats/sticks follow the same native path as buttons.
    @Override public boolean dispatchGenericMotionEvent(MotionEvent e){
        if((e.getSource()&InputDevice.SOURCE_JOYSTICK)==InputDevice.SOURCE_JOYSTICK&&e.getAction()==MotionEvent.ACTION_MOVE){
            // Preserve digital hats, but suppress noisy analog rest values before merging.
            boolean[] old=axes.get(e.getDeviceId());if(old==null)old=new boolean[4];
            int p=player(e.getDeviceId());
            JSONObject assigned=controllerConfig.optJSONObject("effectiveDevices");if(assigned!=null)p=assigned.optInt(controllerKey(e.getDeviceId()),p);
            float[] values={e.getAxisValue(MotionEvent.AXIS_X),e.getAxisValue(MotionEvent.AXIS_Y),e.getAxisValue(MotionEvent.AXIS_Z),e.getAxisValue(MotionEvent.AXIS_RZ)};
            synchronized(rawAxes){rawAxes.put(e.getDeviceId(),values.clone());}
            JSONObject calibrations=controllerConfig.optJSONObject("calibration"),cal=calibrations==null?null:calibrations.optJSONObject(String.valueOf(p));JSONArray center=cal==null?null:cal.optJSONArray("center");if(cal!=null&&!cal.optString("device").equals(controllerKey(e.getDeviceId())))center=null;
            for(int i=0;i<values.length;i++)values[i]=ControllerDirections.normalized(values[i],center==null?0:(float)center.optDouble(i,0));
            boolean[] now=ControllerDirections.update(e.getAxisValue(MotionEvent.AXIS_HAT_X),e.getAxisValue(MotionEvent.AXIS_HAT_Y),0,0,old);
            for(int i=0;i<4;i++)if(now[i]!=old[i]){js("Arcade.nativeKey("+(19+i)+","+now[i]+","+e.getDeviceId()+",true,false)");}
            float[] sent=sentAxes.get(e.getDeviceId());if(sent==null)sent=new float[]{Float.NaN,Float.NaN,Float.NaN,Float.NaN};for(int i=0;i<4;i++)if(Float.isNaN(sent[i])||Math.abs(values[i]-sent[i])>=.025f){sent[i]=values[i];js("Arcade.nativeAxis("+i+","+values[i]+","+e.getDeviceId()+")");}sentAxes.put(e.getDeviceId(),sent);
            boolean[] previousTriggers=triggers.get(e.getDeviceId());if(previousTriggers==null)previousTriggers=new boolean[2];boolean[] nextTriggers={Math.max(e.getAxisValue(MotionEvent.AXIS_LTRIGGER),e.getAxisValue(MotionEvent.AXIS_BRAKE))>.5f,Math.max(e.getAxisValue(MotionEvent.AXIS_RTRIGGER),e.getAxisValue(MotionEvent.AXIS_GAS))>.5f};for(int i=0;i<2;i++)if(nextTriggers[i]!=previousTriggers[i])js("Arcade.nativeKey("+(104+i)+","+nextTriggers[i]+","+e.getDeviceId()+",true,false)");triggers.put(e.getDeviceId(),nextTriggers);axes.put(e.getDeviceId(),now);return true;
        }
        return super.dispatchGenericMotionEvent(e);
    }
    @Override public void onInputDeviceAdded(int id){}
    @Override public void onInputDeviceChanged(int id){}
    @Override public void onInputDeviceRemoved(int id){axes.remove(id);sentAxes.remove(id);triggers.remove(id);synchronized(rawAxes){rawAxes.remove(id);}Integer p=players.remove(id);if(p!=null&&p>0&&nativeNes!=null&&nativeNes.isRunning())nativeNes.pause();js("Arcade.nativeDisconnected("+id+")");}
    @Override protected void onActivityResult(int request,int result,Intent data){
        super.onActivityResult(request,result,data);
        if(request==43||request==44)HallUpdates.result(this,request,result);
        if(request==PICK_PACK&&!fallbackPackActive){if(result==RESULT_OK&&data!=null&&data.getData()!=null)resources.prepare(data.getData());else resources.cancel();}
        if(request==PICK_FILE&&!fallbackFileActive&&chooser!=null){Uri[] uris=null;if(result==RESULT_OK&&data!=null){if(data.getClipData()!=null){int n=data.getClipData().getItemCount();uris=new Uri[n];for(int i=0;i<n;i++)uris[i]=data.getClipData().getItemAt(i).getUri();}else if(data.getData()!=null)uris=new Uri[]{data.getData()};}chooser.onReceiveValue(uris);chooser=null;}
        if(request==EXPORT_FILE&&!fallbackBackupActive){boolean ok=false;if(result==RESULT_OK&&data!=null&&data.getData()!=null&&pendingBackup!=null){try{OutputStream out=getContentResolver().openOutputStream(data.getData());out.write(pendingBackup.getBytes("UTF-8"));out.close();ok=true;}catch(Exception ignored){}}pendingBackup=null;js("Arcade.backupResult("+ok+")");}
    }
    private File keyFile(File dir,String key)throws IOException {if(key==null||!key.matches("[a-z0-9:_-]{1,160}"))throw new IOException("Invalid key");return new File(dir,key+".json");}
    private byte[] readAll(InputStream in,int max)throws IOException{try{ByteArrayOutputStream out=new ByteArrayOutputStream();byte[] buf=new byte[8192];int n;while((n=in.read(buf))!=-1){if(out.size()+n>max)throw new IOException("Data too large");out.write(buf,0,n);}return out.toByteArray();}finally{in.close();}}
    private void atomicWrite(File f,String value)throws IOException {AtomicFile a=new AtomicFile(f);FileOutputStream out=null;try{out=a.startWrite();out.write(value.getBytes("UTF-8"));a.finishWrite(out);}catch(IOException e){if(out!=null)a.failWrite(out);throw e;}}
    private void deleteTree(File file){if(file.isDirectory()){File[] children=file.listFiles();if(children!=null)for(File child:children)deleteTree(child);}file.delete();}
    public String diagLoad(String id){
        try{
            for(String p:new String[]{"nes","arcade","gba","md","sfc"}){
                File gj=new File(new File(externalRoot(this),p),"games.json");
                if(!gj.isFile())continue;
                String json=new String(readAll(new FileInputStream(gj),8*1024*1024),"UTF-8");
                org.json.JSONArray arr=new org.json.JSONArray(json);
                for(int i=0;i<arr.length();i++){
                    org.json.JSONObject g=arr.getJSONObject(i);
                    if(id.equals(g.optString("id"))){
                        String path=g.getString("path");
                        String name=path.substring(path.lastIndexOf('/')+1);
                        String hash=g.getString("hash");
                        String sys=g.optString("system","nes");
                        String res;
                        if("gba".equals(sys))res=nativeNes.loadGba(name,hash);
                        else if("md".equals(sys))res=nativeNes.loadMd(name,hash);
                        else if("sfc".equals(sys))res=nativeNes.loadSfc(name,hash);
                        else if("nes".equals(sys))res=nativeNes.load(Base64.encodeToString(readAll(new FileInputStream(new File(new File(externalRoot(this),p),"roms/"+name)),8*1024*1024),Base64.NO_WRAP),hash);
                        else if("mame".equals(sys))res=nativeNes.loadMame(name,hash);
                        else res=nativeNes.loadArcade(name,hash);
                        return res;
                    }
                }
            }
            return "{\"error\":\"game not found\"}";
        }catch(Throwable e){return "{\"error\":\""+e.getMessage()+"\"}";}
    }
    public class Bridge {
        @JavascriptInterface public String platformInfo(){String version="未知";try{version=getPackageManager().getPackageInfo(getPackageName(),0).versionName;}catch(Exception ignored){}return "{\"api\":"+android.os.Build.VERSION.SDK_INT+",\"version\":"+JSONObject.quote(version)+"}";}
        @JavascriptInterface public void configureControllers(String json){try{controllerConfig=new JSONObject(json);runOnUiThread(new Runnable(){public void run(){axes.clear();sentAxes.clear();}});}catch(Exception ignored){}}
        @JavascriptInterface public String controllerSnapshot(){JSONArray rows=new JSONArray();synchronized(rawAxes){for(Integer id:rawAxes.keySet())try{JSONArray a=new JSONArray();for(float v:rawAxes.get(id))a.put(v);rows.put(new JSONObject().put("id",id).put("key",controllerKey(id)).put("player",players.containsKey(id)?players.get(id):1).put("axes",a));}catch(Exception ignored){}}return rows.toString();}
        @JavascriptInterface public String resourceState(){try{return resources.state();}catch(Exception e){return "{}";}}
        @JavascriptInterface public String resourceVersion(){try{return resources.version();}catch(Exception e){return "";}}
        @JavascriptInterface public String resourcePresence(String json){try{return resources.presence(json);}catch(Exception e){return "{}";}}
        @JavascriptInterface public String importedGames(){try{return resources.games().toString();}catch(Exception e){return "[]";}}
        @JavascriptInterface public String readPacked(String hash){try{if(!hash.matches("[a-f0-9]{64}"))return null;File f=resources.resolve(hash);return f==null?null:Base64.encodeToString(readAll(new FileInputStream(f),8*1024*1024),Base64.NO_WRAP);}catch(Exception e){return null;}}
        @JavascriptInterface public String beginPackImport(){resources.waiting();runOnUiThread(new Runnable(){public void run(){Intent i=new Intent(Intent.ACTION_OPEN_DOCUMENT);i.addCategory(Intent.CATEGORY_OPENABLE);i.setType("application/zip");fallbackPackActive=false;try{startActivityForResult(i,PICK_PACK);}catch(ActivityNotFoundException e){fallbackPackActive=true;new LegacyPackPicker(MainActivity.this).start();}}});return resources.status();}
        @JavascriptInterface public String beginResourceUpdate(final String json){resources.waiting();new Thread(new Runnable(){public void run(){File zip=new File(getCacheDir(),"download-resources.zip");try{JSONObject r=new JSONObject(json);long bytes=r.getLong("bytes");if(bytes<1||bytes>2147483647L||getCacheDir().getUsableSpace()<bytes*2+10485760)throw new IOException("本机剩余空间不足");resources.downloading(0,bytes);long received=HallUpdates.downloadFile(r.getString("url"),zip,bytes,new HallUpdates.Progress(){public void received(long n,long total){resources.downloading(n,total);}});if(received!=bytes||!HallUpdates.fileDigest(zip).equals(r.getString("sha256")))throw new IOException("资源下载校验失败");resources.prepare(Uri.fromFile(zip));}catch(Exception e){zip.delete();resources.fail(e.getMessage());}}},"resource-download").start();return resources.status();}
        @JavascriptInterface public String packImportStatus(){return resources.status();}
        @JavascriptInterface public String commitPackImport(){return resources.commit();}
        @JavascriptInterface public void cancelPackImport(){resources.cancel();}
        @JavascriptInterface public void setSmoothing(boolean value){nativeNes.setSmoothing(value);}
        @JavascriptInterface public String gameRoot(){return externalRoot(MainActivity.this);}
        @JavascriptInterface public void setGameRoot(String path){if(path!=null&&path.length()>0&&!path.contains(".."))setExternalRoot(MainActivity.this,path);}
        @JavascriptInterface public void pickGameRoot(){runOnUiThread(new Runnable(){public void run(){new RootPicker(MainActivity.this,new RootPicker.Callback(){public void picked(String path){setExternalRoot(MainActivity.this,path);js("Arcade.gameRootChanged('"+path.replace("'","")+"')");}}).start();}});}
        @JavascriptInterface public String fetchUpdate(String url){try{return new String(HallUpdates.download(url,2097152),"UTF-8");}catch(Exception e){return "{\"error\":\"更新清单无法读取，请检查网络后重试\"}";}}
        @JavascriptInterface public String prepareAppUpdate(String json){return HallUpdates.prepare(MainActivity.this,json);}
        @JavascriptInterface public void beginAppUpdate(String json){HallUpdates.begin(MainActivity.this,json);}
        @JavascriptInterface public String appUpdateStatus(){return HallUpdates.status(MainActivity.this);}
        @JavascriptInterface public void completeAppUpdate(){HallUpdates.complete(MainActivity.this);}
        @JavascriptInterface public String verifyImportedResources(){try{return resources.verifyInstalled();}catch(Exception e){return JSONObject.quote(e.getMessage());}}
        @JavascriptInterface public String checkGame(String json){try{JSONObject g=new JSONObject(json);String path=g.getString("path");if(path.contains("..")||path.startsWith("/"))throw new IOException("路径无效");File f=new File(externalRoot(MainActivity.this),path);if(!f.isFile())throw new IOException("文件缺失");String hash=HallUpdates.fileDigest(f);if(!hash.equals(g.getString("hash")))return JSONObject.quote(g.getString("title")+"：校验失败");String dependency=HallResources.dependencyError(g,f);return dependency==null?"null":JSONObject.quote(g.getString("title")+"："+dependency);}catch(Exception e){return JSONObject.quote("文件缺失或无法读取");}}

        @JavascriptInterface public boolean nativeNesAvailable(){return new File(getApplicationInfo().nativeLibraryDir,"libfceumm.so").isFile();}
        @JavascriptInterface public String nativeSfcStart(String name,String hash){return nativeNes.loadSfc(name,hash);}
        @JavascriptInterface public String nativeMdStart(String name,String hash){return nativeNes.loadMd(name,hash);}
        @JavascriptInterface public String nativeGbaStart(String name,String hash){return nativeNes.loadGba(name,hash);}
        @JavascriptInterface public String nativeArcadeStart(String name,String hash){return nativeNes.loadArcade(name,hash);}
        @JavascriptInterface public String nativeMameStart(String name,String hash){return nativeNes.loadMame(name,hash);}
        @JavascriptInterface public String nativeNesStart(String data,String hash){return nativeNes.load(data,hash);}
        @JavascriptInterface public void nativeNesPause(){nativeNes.pause();}
        @JavascriptInterface public void nativeNesResume(){nativeNes.resume();}
        @JavascriptInterface public void nativeNesClose(){nativeNes.close();}
        @JavascriptInterface public void nativeNesButton(int player,int button,boolean down){nativeNes.button(player,button,down);}
        @JavascriptInterface public void nativeNesRelease(){nativeNes.releaseAll();}
        @JavascriptInterface public void nativeNesVolume(float value){nativeNes.volume(value);}
        @JavascriptInterface public void nativeNesShader(int mode){nativeNes.shader(mode);}
        @JavascriptInterface public boolean nativeNesVertical(){return nativeNes.isVertical();}
        @JavascriptInterface public void nativeNesBounds(float left,float top,float width,float height,float viewportWidth,float viewportHeight){nativeNes.bounds(left,top,width,height,viewportWidth,viewportHeight);}
        @JavascriptInterface public String nativeNesSnapshot(){return nativeNes.snapshot();}
        @JavascriptInterface public String nativeNesRestore(String value){return nativeNes.restore(value);}
        @JavascriptInterface public String nativeNesImage(){return nativeNes.image();}
        @JavascriptInterface public String nativeNesStats(){return nativeNes.stats();}
        @JavascriptInterface public String readAsset(String path){if(path==null||path.contains("..")||path.startsWith("/"))return null;String root=externalRoot(MainActivity.this);File ext=new File(root,path);if(!ext.isFile())ext=new File(new File(root,"nes"),path);if(ext.isFile())try{return Base64.encodeToString(readAll(new FileInputStream(ext),8*1024*1024),Base64.NO_WRAP);}catch(Exception e){return null;}if(!path.matches("roms/[a-z0-9-]+\\.nes"))return null;try{return Base64.encodeToString(readAll(getAssets().open(path),8*1024*1024),Base64.NO_WRAP);}catch(Exception e){return null;}}
        @JavascriptInterface public String readStore(String key){synchronized(storeLock){try{File f=keyFile(storeDir,key);if(!f.exists())return null;return new String(readAll(new AtomicFile(f).openRead(),32*1024*1024),"UTF-8");}catch(Exception e){return "{\"__readError\":true}";}}}
        @JavascriptInterface public boolean writeStore(String key,String value){synchronized(storeLock){try{if(value==null||value.length()>32*1024*1024)return false;new JSONObject("{\"value\":"+value+"}");atomicWrite(keyFile(storeDir,key),value);return true;}catch(Exception e){return false;}}}
        @JavascriptInterface public String appAbi(){String arch=System.getProperty("os.arch", "");if(arch.equals("aarch64")||arch.equals("arm64"))return "arm64-v8a";if(arch.startsWith("arm"))return "armeabi-v7a";return "unknown";}
        @JavascriptInterface public String migrateLegacyNes(){synchronized(storeLock){try{int count=0;for(LegacyNesSaves.Item item:LegacyNesSaves.read(new File(getFilesDir(),"nes"),storeDir)){JSONObject value=new JSONObject().put("schema",1).put("format","nes-sram-base64").put("hash",item.hash).put("engine","fceumm-native-81ebd3e72d96").put("bytes",item.data.length).put("sha256",HallUpdates.streamDigest(new ByteArrayInputStream(item.data))).put("data",Base64.encodeToString(item.data,Base64.NO_WRAP));atomicWrite(keyFile(storeDir,"battery:"+item.hash),value.toString());count++;}return new JSONObject().put("migrated",count).toString();}catch(Exception e){return "{\"error\":\"旧游戏内存档备份准备失败，原文件已保留\"}";}}}
        @JavascriptInterface public String listStoreKeys(){synchronized(storeLock){JSONArray list=new JSONArray();File[] files=storeDir.listFiles();if(files!=null)for(File f:files)if(f.getName().endsWith(".json"))list.put(f.getName().substring(0,f.getName().length()-5));return list.toString();}}
        @JavascriptInterface public boolean writeBatch(String json){synchronized(storeLock){File stage=new File(getFilesDir(),"store.stage"),old=new File(getFilesDir(),"store.previous");boolean moved=false;try{
            JSONArray entries=new JSONArray(json);if(entries.length()>1000)return false;deleteTree(stage);stage.mkdirs();File[] originals=storeDir.listFiles();if(originals!=null)for(File f:originals)if(f.isFile()&&f.getName().endsWith(".json"))atomicWrite(new File(stage,f.getName()),new String(readAll(new FileInputStream(f),32*1024*1024),"UTF-8"));
            for(int i=0;i<entries.length();i++){JSONObject entry=entries.getJSONObject(i);String key=entry.getString("key");if(!key.equals("prefs")&&!key.equals("hall-v2")&&!key.matches("slot:[a-f0-9]{64}:[0-3]|battery:[a-f0-9]{64}"))throw new IOException("Invalid backup key");atomicWrite(keyFile(stage,key),entry.getJSONObject("value").toString());}
            deleteTree(old);if(!storeDir.renameTo(old))throw new IOException("Cannot stage original");moved=true;if(!stage.renameTo(storeDir))throw new IOException("Cannot commit backup");deleteTree(old);return true;
        }catch(Exception e){if(moved&&!storeDir.exists())old.renameTo(storeDir);deleteTree(stage);return false;}}}
        @JavascriptInterface public void finishApp(){runOnUiThread(new Runnable(){public void run(){finish();}});}
        @JavascriptInterface public void exportBackup(final String json){runOnUiThread(new Runnable(){public void run(){if(json==null||json.length()>50*1024*1024){js("Arcade.backupResult(false)");return;}pendingBackup=json;Intent intent=new Intent(Intent.ACTION_CREATE_DOCUMENT);intent.addCategory(Intent.CATEGORY_OPENABLE);intent.setType("application/json");intent.putExtra(Intent.EXTRA_TITLE,"童年游戏厅_存档备份.json");fallbackBackupActive=false;try{startActivityForResult(intent,EXPORT_FILE);}catch(ActivityNotFoundException e){fallbackBackupActive=true;new LegacyBackupExporter(MainActivity.this).start();}}});}
    }
}
