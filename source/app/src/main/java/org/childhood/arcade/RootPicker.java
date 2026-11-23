package org.childhood.arcade;

import android.app.AlertDialog;
import android.content.DialogInterface;
import android.os.Environment;
import java.io.File;
import java.util.ArrayList;
import java.util.Collections;
import java.util.Comparator;
import java.util.Locale;

/** Browse a storage folder and report the chosen game root back to the hall. */
final class RootPicker {
 interface Callback { void picked(String path); }
 private final MainActivity activity;
 private final Callback callback;
 RootPicker(MainActivity activity, Callback callback){this.activity=activity;this.callback=callback;}

 void start(){
  File base=Environment.getExternalStorageDirectory();
  browse(base!=null&&base.isDirectory()?base:new File("/sdcard"), null);
 }

 private void browse(final File dir, final File back){
  File[] all=dir.listFiles();
  if(all==null){fail();return;}
  final ArrayList<File> dirs=new ArrayList<File>();
  for(File f:all)if(f.isDirectory()&&!f.isHidden())dirs.add(f);
  Collections.sort(dirs,new Comparator<File>(){public int compare(File a,File b){return a.getName().compareToIgnoreCase(b.getName());}});
  final ArrayList<CharSequence> labels=new ArrayList<CharSequence>();
  if(back!=null)labels.add("← 返回上级");
  labels.add("使用此目录："+dir.getAbsolutePath());
  for(File f:dirs)labels.add("[文件夹] "+f.getName());
  new AlertDialog.Builder(activity).setTitle("选择游戏目录").setItems(labels.toArray(new CharSequence[0]),new DialogInterface.OnClickListener(){public void onClick(DialogInterface d,int n){
    if(back!=null&&n==0){browse(back,null);return;}
    int idx=back!=null?n-1:n;
    if(idx==0){callback.picked(dir.getAbsolutePath());return;}
    browse(dirs.get(idx-1),dir);
  }}).setNegativeButton("取消",new DialogInterface.OnClickListener(){public void onClick(DialogInterface d,int n){}}).show();
 }
 private void fail(){android.widget.Toast.makeText(activity,"无法读取该位置，请检查存储权限",android.widget.Toast.LENGTH_LONG).show();}
}
