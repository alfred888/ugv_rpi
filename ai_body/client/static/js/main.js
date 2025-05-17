// 页面加载完成后执行
document.addEventListener('DOMContentLoaded', function() {
    console.log('页面已加载完成');
});

// 基本的错误处理
window.onerror = function(msg, url, line) {
    console.error('错误: ' + msg + '\nURL: ' + url + '\n行号: ' + line);
    return false;
}; 