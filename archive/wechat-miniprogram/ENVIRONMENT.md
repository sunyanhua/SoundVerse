# 微信小程序环境配置说明

## 环境类型
小程序支持三种环境配置：

1. **local** - 本机开发环境
   - 默认API地址：`http://localhost:8000`
   - 适用于微信开发者工具连接本地后端服务
   - 可通过调试页面设置自定义本地IP地址

2. **dev** - 公网测试环境
   - 默认API地址：`http://dev-api.soundverse.example.com`
   - 适用于体验版小程序测试

3. **prod** - 正式上线环境
   - 默认API地址：`https://api.soundverse.example.com`
   - 适用于正式发布的小程序

## 环境自动检测规则

小程序会自动根据微信账号信息检测当前环境：

| 微信环境 | 映射到 | 说明 |
|----------|--------|------|
| develop  | local  | 开发者工具 |
| trial    | dev    | 体验版 |
| release  | prod   | 正式版 |

## 手动环境切换

可以通过以下方式手动切换环境：

1. **在代码中调用**：
```typescript
import { setManualEnvironment } from './config';

// 切换到local环境
setManualEnvironment('local');

// 切换到dev环境
setManualEnvironment('dev');

// 切换到prod环境
setManualEnvironment('prod');

// 清除手动设置，恢复自动检测
clearManualEnvironment();
```

2. **通过调试页面**：
   - 访问 `/pages/debug/debug` 页面
   - 点击环境切换按钮
   - 查看当前环境信息
   - 测试API连接

## 自定义本地API地址

当使用local环境时，可以设置自定义的本地API地址：

```typescript
import { setLocalBaseUrl } from './config';

// 设置自定义本地地址（如指定局域网IP）
setLocalBaseUrl('http://192.168.1.100:8000');

// 清除自定义地址
clearLocalBaseUrl();
```

也可以通过调试页面设置自定义地址。

## 配置优先级

1. 手动环境设置（最高优先级）
2. 微信环境自动检测
3. 默认local环境（最低优先级）

## 验证环境配置

1. 查看控制台日志，检查环境检测结果
2. 访问调试页面查看当前环境信息
3. 测试API连接是否正常

## 注意事项

1. 生产环境请确保使用HTTPS
2. 本地开发时注意CORS配置
3. 环境切换后需要重新加载页面使配置生效