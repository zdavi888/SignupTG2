'use client';

import { useState } from 'react';

export default function SyncPage() {
  const [syncing, setSyncing] = useState(false);
  const [message, setMessage] = useState('');
  const LOCAL_PORT = 5044; // Changed port to avoid 5033 conflict

  const handleSync = async () => {
    setSyncing(true);
    setMessage('正在从云端获取最新代码...');
    
    try {
      // 1. Fetch latest files from the cloud backend
      const res = await fetch('/api/sync-files');
      if (!res.ok) {
        throw new Error('获取云端代码失败');
      }
      const data = await res.json();
      
      if (!data.files) {
        throw new Error('未获取到文件列表');
      }

      setMessage(`获取成功，开始向本地 (127.0.0.1:${LOCAL_PORT}) 推送...`);

      // 2. Push to local python script via browser
      const localRes = await fetch(`http://127.0.0.1:${LOCAL_PORT}/sync`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ files: data.files })
      });

      if (!localRes.ok) {
        throw new Error('推送到本地失败，请检查本地脚本是否运行。');
      }

      setMessage('代码同步成功！请在本地终端查看。');
    } catch (err: any) {
      console.error(err);
      setMessage(`同步失败: ${err.message}`);
    } finally {
      setSyncing(false);
    }
  };

  return (
    <div className="min-h-screen flex flex-col items-center justify-center bg-gray-50 p-4">
      <div className="max-w-md w-full bg-white rounded-xl shadow-lg p-8 text-center space-y-6">
        <h1 className="text-2xl font-bold text-gray-800">雷电自动化同步控制台</h1>
        <p className="text-gray-600 text-sm">
          点击下方按钮，将云端最新的代码推送到您本地电脑上运行的交互脚本中。
        </p>
        
        <button
          onClick={handleSync}
          disabled={syncing}
          className={`w-full py-3 px-4 rounded-lg font-medium text-white transition-colors
            ${syncing ? 'bg-blue-400 cursor-not-allowed' : 'bg-blue-600 hover:bg-blue-700 active:bg-blue-800'}`}
        >
          {syncing ? '正在同步...' : '同步推送代码到本地'}
        </button>

        {message && (
          <div className={`p-4 rounded-md text-sm text-left ${message.includes('失败') ? 'bg-red-50 text-red-700' : 'bg-green-50 text-green-700'}`}>
            {message}
          </div>
        )}
      </div>
    </div>
  );
}
