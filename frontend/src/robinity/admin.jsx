import React, { useEffect, useState } from "react";
import { ethers } from "ethers";
import { PublicFooter, PublicHeader } from "./landing.jsx";
import ApiMonitor from "./api-monitor.jsx";
import { TEST_ADMIN_ARTIFACTS } from "./admin-artifacts.js";

const NETWORKS = {
  mainnet: {
    id: 4663,
    name: "Robinhood Chain Mainnet",
    short: "mainnet",
    rpc: "https://rpc.mainnet.chain.robinhood.com",
    explorer: "https://robinhoodchain.blockscout.com"
  },
  testnet: {
    id: 46630,
    name: "Robinhood Chain Testnet",
    short: "testnet",
    rpc: "https://rpc.testnet.chain.robinhood.com",
    explorer: "https://explorer.testnet.chain.robinhood.com"
  }
};

const TRANSLATIONS = {
  en: {
    protectedWorkspace: "Protected workspace",
    adminAccess: "Admin access",
    setUpAuth: "Set up authenticator",
    enterAuthCode: "Enter authenticator code",
    connectWallet: "Connect admin wallet",
    preparingAuth: "Preparing authenticator setup…",
    scanQrNotice: "Scan the QR code in Google Authenticator, then enter the current 6-digit code.",
    enterCodeNotice: "Enter the current 6-digit authenticator code to continue.",
    verify: "Verify",
    walletExtensionRequired: "An EVM wallet extension (e.g. MetaMask, Rabby) is required.",
    subtitle: "Curve Operations & Infrastructure",
    title: "Robinity Intelligence Admin",
    refreshAll: "↻ Refresh All",
    activeNetwork: "Active Network:",
    walletNotConnected: "Wallet not connected",
    unsupported: "Unsupported",
    switchTestnet: "Robinhood Testnet (46630)",
    switchMainnet: "Robinhood Mainnet (4663)",
    tabCurve: "🚀 Curve & Deploy",
    tabApi: "🔑 API Key Pool",
    tabAdmins: "👥 Administrators",
    tabActivity: "📜 Activity Log",
    deploymentSelection: "Saved Deployment Selection",
    newDeployment: "+ New Deployment",
    selectDeploymentPlaceholder: "-- Choose a saved deployment --",
    deploymentLabel: "Deployment & Token Name",
    deploymentLabelPlaceholder: "e.g. Robinity Intelligence Alpha",
    tokenSymbol: "Token Symbol",
    tokenSymbolPlaceholder: "e.g. RBNT",
    saveAddresses: "Save Addresses & Settings",
    savedDeploymentInfo: "Selected {label} on {network}",
    readyNewDeployment: "Ready to configure a new deployment.",
    deployContracts: "Deploy Contracts",
    liveEthUsd: "Coinbase Live ETH / USD Quote",
    priceLoading: "Loading live quote…",
    useLivePrice: "Use Live Price",
    initialEthUsd: "Initial ETH / USD Rate",
    initialEthUsdPlaceholder: "e.g. 2500.00",
    deployButton: "Deploy Token + Curve",
    deployButtonNamed: "Deploy {name} Token + Curve",
    deploying: "Deploying Contracts…",
    activeTokenAddress: "Active Token Address",
    tokenAddressPlaceholder: "0x… (Auto-filled after deployment, or paste existing)",
    activeCurveAddress: "Active Curve Address",
    curveAddressPlaceholder: "0x… (Auto-filled after deployment, or paste existing)",
    wireAndFund: "Set Token & Fund Curve (200M)",
    liveCurveStatus: "Curve Live State",
    refresh: "↻ Refresh",
    incomingFunds: "Incoming Funds (Index)",
    tokensSold: "Tokens Sold",
    saleStatus: "Sale Status",
    claimsStatus: "Claims Status",
    open: "Open",
    closed: "Closed",
    curveEthUsdRate: "Curve ETH / USD Rate",
    updateRate: "Update Rate",
    toggleSale: "Toggle Sale",
    toggleClaims: "Toggle Claims",
    closeSale: "Close Sale",
    openSale: "Open Sale",
    closeClaims: "Close Claims",
    openClaims: "Open Claims",
    treasuryActions: "Treasury Actions",
    withdrawAmountEth: "Withdraw Amount (ETH)",
    withdraw: "Withdraw ETH",
    withdraw99: "Withdraw 99% to Treasury",
    treasuryNotice: "Note: 99% withdrawal operates before bonding completes; funds are swept directly to the treasury wallet.",
    testActions: "Test Wallet Actions",
    buyAmountEth: "Buy Amount (ETH)",
    buyTokens: "Buy Tokens",
    claimTokens: "Claim Tokens",
    testNotice: "Simulate purchase and claim allocated tokens directly on the testnet with connected wallet.",
    configuredProviders: "configured providers",
    trackedRequests: "tracked requests",
    keysInRotation: "keys in rotation",
    keysInCooldown: "keys in cooldown",
    vaultKeys: "Vault Keys",
    noVaultKeys: "No vault keys added yet. Keys defined in .env operate automatically.",
    requests: "requests",
    active: "active",
    paused: "paused",
    inPool: "In Pool",
    cooldownUntil: "Cooldown until: ",
    expires: "Expires: ",
    rotate: "Rotate",
    pause: "Pause",
    activate: "Activate",
    delete: "Delete",
    confirmDeleteKey: "Remove this encrypted API key?",
    rotatePrompt: "Paste replacement API key secret:",
    addApiKey: "Add New API Key",
    providerPlaceholder: "Provider (e.g. Helius, Etherscan, GoPlus, Bitquery)",
    labelPlaceholder: "Label (e.g. production-key-1)",
    secretPlaceholder: "Secret Key (encrypted with AES-256 at rest)",
    monthlyLimitPlaceholder: "Monthly Request Limit (Optional)",
    expiresPlaceholder: "Expiration Date (Optional)",
    storeEncryptedKey: "Store Encrypted Key",
    addAdmin: "Add Administrator",
    adminWalletPlaceholder: "0x… Ethereum wallet address",
    addAdminButton: "Add Administrator",
    authorizedAdmins: "Authorized Administrators",
    authEnrolled: "✔ Authenticator enrolled",
    authPending: "⏳ Authenticator pending",
    activityLog: "Activity Log",
    filter: "Filter:",
    filterAll: "All Networks & States",
    filterMainnet: "Mainnet Only",
    filterTestnet: "Testnet Only",
    filterPending: "Pending Only",
    filterConfirmed: "Confirmed Only",
    filterFailed: "Failed Only",
    noActivity: "No activity records found."
  },
  tr: {
    protectedWorkspace: "Korumalı çalışma alanı",
    adminAccess: "Yönetici girişi",
    setUpAuth: "İki aşamalı doğrulayıcıyı (TOTP) kur",
    enterAuthCode: "Doğrulayıcı kodunu gir",
    connectWallet: "Yönetici cüzdanını bağla",
    preparingAuth: "Doğrulayıcı kurulumu hazırlanıyor…",
    scanQrNotice: "QR kodu Google Authenticator ile tarayın, ardından 6 haneli kodu girin.",
    enterCodeNotice: "Devam etmek için mevcut 6 haneli doğrulayıcı kodunu girin.",
    verify: "Doğrula",
    walletExtensionRequired: "Bir EVM cüzdan uzantısı (MetaMask, Rabby vb.) gereklidir.",
    subtitle: "Curve Operasyonları & Altyapı",
    title: "Robinity Intelligence Yönetim Paneli",
    refreshAll: "↻ Tümünü Yenile",
    activeNetwork: "Aktif Ağ:",
    walletNotConnected: "Cüzdan bağlı değil",
    unsupported: "Desteklenmeyen Ağ",
    switchTestnet: "Robinhood Testnet (46630)",
    switchMainnet: "Robinhood Mainnet (4663)",
    tabCurve: "🚀 Curve & Deploy Yönetimi",
    tabApi: "🔑 API Key Havuzu",
    tabAdmins: "👥 Yöneticiler",
    tabActivity: "📜 İşlem Geçmişi",
    deploymentSelection: "Kayıtlı Deployment Seçimi",
    newDeployment: "+ Yeni Deployment",
    selectDeploymentPlaceholder: "-- Kayıtlı bir deployment seçin --",
    deploymentLabel: "Deployment ve Token Adı",
    deploymentLabelPlaceholder: "Örn: Robinity Intelligence Alpha",
    tokenSymbol: "Token Sembolü",
    tokenSymbolPlaceholder: "Örn: RBNT",
    saveAddresses: "Adresleri & Ayarları Kaydet",
    savedDeploymentInfo: "{network} üzerinde {label} seçildi",
    readyNewDeployment: "Yeni bir deployment yapılandırmak için hazır.",
    deployContracts: "Sözleşmeleri Dağıt (Deploy)",
    liveEthUsd: "Coinbase Canlı ETH / USD Kuru",
    priceLoading: "Canlı kur alınıyor…",
    useLivePrice: "Canlı Fiyatı Kullan",
    initialEthUsd: "Başlangıç ETH / USD Kuru",
    initialEthUsdPlaceholder: "Örn: 2500.00",
    deployButton: "Token + Curve Dağıt",
    deployButtonNamed: "{name} Token + Curve Dağıt",
    deploying: "Sözleşmeler Dağıtılıyor…",
    activeTokenAddress: "Aktif Token Adresi",
    tokenAddressPlaceholder: "0x… (Dağıtım sonrası otomatik dolar veya mevcut adresi yapıştırın)",
    activeCurveAddress: "Aktif Curve Adresi",
    curveAddressPlaceholder: "0x… (Dağıtım sonrası otomatik dolar veya mevcut adresi yapıştırın)",
    wireAndFund: "Token'ı Ata ve Curve'e 200M Fonla",
    liveCurveStatus: "Curve Canlı Durumu",
    refresh: "↻ Yenile",
    incomingFunds: "Gelen Fon (Index)",
    tokensSold: "Satılan Token",
    saleStatus: "Satış Durumu",
    claimsStatus: "Claim Durumu",
    open: "Açık",
    closed: "Kapalı",
    curveEthUsdRate: "Curve ETH / USD Kuru",
    updateRate: "Kuru Güncelle",
    toggleSale: "Satışı Değiştir",
    toggleClaims: "Claim'leri Değiştir",
    closeSale: "Satışı Kapat",
    openSale: "Satışı Aç",
    closeClaims: "Claim'leri Kapat",
    openClaims: "Claim'leri Aç",
    treasuryActions: "Treasury (Hazine) İşlemleri",
    withdrawAmountEth: "Çekilecek ETH Miktarı",
    withdraw: "ETH Çek",
    withdraw99: "%99 Hazineye Çek",
    treasuryNotice: "Not: %99 çekme işlemi bonding bitmeden de çalışır; bakiye doğrudan hazine cüzdanına aktarılır.",
    testActions: "Test Cüzdan İşlemleri",
    buyAmountEth: "Alım Miktarı (ETH)",
    buyTokens: "Token Satın Al",
    claimTokens: "Token Claim Et",
    testNotice: "Bağlı cüzdan ile testnet üzerinde alım simülasyonu ve hak edilen token'ların teslim alınması.",
    configuredProviders: "yapılandırılmış sağlayıcı",
    trackedRequests: "takip edilen istek",
    keysInRotation: "rotasyondaki anahtar",
    keysInCooldown: "soğumadaki anahtar",
    vaultKeys: "Kasa Anahtarları (Vault Keys)",
    noVaultKeys: "Henüz kasa anahtarı eklenmemiş. .env üzerindeki anahtarlar otomatik çalışmaktadır.",
    requests: "istek",
    active: "aktif",
    paused: "durduruldu",
    inPool: "Havuzda",
    cooldownUntil: "Soğuma bitişi: ",
    expires: "Bitiş: ",
    rotate: "Değiştir",
    pause: "Durdur",
    activate: "Aktifleştir",
    delete: "Sil",
    confirmDeleteKey: "Bu şifreli API anahtarı kaldırılsın mı?",
    rotatePrompt: "Yeni API anahtarı gizli değerini yapıştırın:",
    addApiKey: "Yeni API Anahtarı Ekle",
    providerPlaceholder: "Sağlayıcı (Örn: Helius, Etherscan, GoPlus, Bitquery)",
    labelPlaceholder: "Etiket (Örn: production-key-1)",
    secretPlaceholder: "Gizli Anahtar (AES-256 ile şifrelenir)",
    monthlyLimitPlaceholder: "Aylık İstek Limiti (Opsiyonel)",
    expiresPlaceholder: "Son Kullanma Tarihi (Opsiyonel)",
    storeEncryptedKey: "Şifreli Anahtarı Kaydet",
    addAdmin: "Yeni Yönetici Ekle",
    adminWalletPlaceholder: "0x… Ethereum cüzdan adresi",
    addAdminButton: "Yönetici Ekle",
    authorizedAdmins: "Yetkili Yöneticiler",
    authEnrolled: "✔ Authenticator devrede",
    authPending: "⏳ Authenticator bekleniyor",
    activityLog: "Aktivite ve İşlem Geçmişi",
    filter: "Filtre:",
    filterAll: "Tüm Ağlar ve Durumlar",
    filterMainnet: "Yalnızca Mainnet",
    filterTestnet: "Yalnızca Testnet",
    filterPending: "Bekleyenler (Pending)",
    filterConfirmed: "Onaylananlar (Confirmed)",
    filterFailed: "Başarısızlar (Failed)",
    noActivity: "Henüz kayıtlı aktivite bulunmamaktadır."
  },
  zh: {
    protectedWorkspace: "受保护的工作空间",
    adminAccess: "管理员访问",
    setUpAuth: "设置双重身份验证器 (TOTP)",
    enterAuthCode: "输入身份验证代码",
    connectWallet: "连接管理员钱包",
    preparingAuth: "正在准备身份验证器设置…",
    scanQrNotice: "在 Google Authenticator 中扫描二维码，然后输入 6 位代码。",
    enterCodeNotice: "输入当前 6 位验证码以继续。",
    verify: "验证",
    walletExtensionRequired: "需要 EVM 钱包扩展（如 MetaMask、Rabby）。",
    subtitle: "Curve 运营与基础设施",
    title: "Robinity Intelligence 管理面板",
    refreshAll: "↻ 全部刷新",
    activeNetwork: "当前网络：",
    walletNotConnected: "未连接钱包",
    unsupported: "不支持的网络",
    switchTestnet: "Robinhood 测试网 (46630)",
    switchMainnet: "Robinhood 主网 (4663)",
    tabCurve: "🚀 Curve 与部署管理",
    tabApi: "🔑 API 密钥池",
    tabAdmins: "👥 管理员",
    tabActivity: "📜 操作日志",
    deploymentSelection: "已保存的部署选择",
    newDeployment: "+ 新建部署",
    selectDeploymentPlaceholder: "-- 选择已保存的部署 --",
    deploymentLabel: "部署与代币名称",
    deploymentLabelPlaceholder: "例如：Robinity Intelligence Alpha",
    tokenSymbol: "代币符号",
    tokenSymbolPlaceholder: "例如：RBNT",
    saveAddresses: "保存地址与设置",
    savedDeploymentInfo: "已选择 {network} 上的 {label}",
    readyNewDeployment: "准备配置新部署。",
    deployContracts: "部署智能合约",
    liveEthUsd: "Coinbase 实时 ETH / USD 报价",
    priceLoading: "正在获取实时报价…",
    useLivePrice: "使用实时价格",
    initialEthUsd: "初始 ETH / USD 汇率",
    initialEthUsdPlaceholder: "例如：2500.00",
    deployButton: "部署代币与 Curve",
    deployButtonNamed: "部署 {name} 代币与 Curve",
    deploying: "正在部署合约…",
    activeTokenAddress: "当前代币地址",
    tokenAddressPlaceholder: "0x…（部署后自动填充，或粘贴已有地址）",
    activeCurveAddress: "当前 Curve 地址",
    curveAddressPlaceholder: "0x…（部署后自动填充，或粘贴已有地址）",
    wireAndFund: "设置代币并注资 200M",
    liveCurveStatus: "Curve 实时状态",
    refresh: "↻ 刷新",
    incomingFunds: "累计筹集 (Index)",
    tokensSold: "已售代币",
    saleStatus: "销售状态",
    claimsStatus: "认领状态",
    open: "开启",
    closed: "关闭",
    curveEthUsdRate: "Curve ETH / USD 汇率",
    updateRate: "更新汇率",
    toggleSale: "切换销售开关",
    toggleClaims: "切换认领开关",
    closeSale: "关闭销售",
    openSale: "开启销售",
    closeClaims: "关闭认领",
    openClaims: "开启认领",
    treasuryActions: "金库操作",
    withdrawAmountEth: "提取数量 (ETH)",
    withdraw: "提取 ETH",
    withdraw99: "向金库提取 99%",
    treasuryNotice: "注意：在联合曲线未结束前也可提取 99%；资金将直接转入金库钱包。",
    testActions: "测试操作",
    buyAmountEth: "购买数量 (ETH)",
    buyTokens: "购买代币",
    claimTokens: "认领代币",
    testNotice: "使用已连接的钱包在测试网上模拟购买并认领已分配的代币。",
    configuredProviders: "已配置提供商",
    trackedRequests: "已跟踪请求数",
    keysInRotation: "轮换中密钥",
    keysInCooldown: "冷却中密钥",
    vaultKeys: "保险库密钥",
    noVaultKeys: "尚未添加保险库密钥。.env 中配置的密钥会自动生效。",
    requests: "次请求",
    active: "活跃",
    paused: "已暂停",
    inPool: "在池中",
    cooldownUntil: "冷却至：",
    expires: "过期时间：",
    rotate: "更换密钥",
    pause: "暂停",
    activate: "启用",
    delete: "删除",
    confirmDeleteKey: "确定删除此加密 API 密钥吗？",
    rotatePrompt: "粘贴替换的 API 密钥密文：",
    addApiKey: "添加新 API 密钥",
    providerPlaceholder: "提供商（例如：Helius, Etherscan, GoPlus, Bitquery）",
    labelPlaceholder: "标签（例如：production-key-1）",
    secretPlaceholder: "密钥值（静态存储使用 AES-256 加密）",
    monthlyLimitPlaceholder: "月度请求限额（可选）",
    expiresPlaceholder: "过期日期（可选）",
    storeEncryptedKey: "存储加密密钥",
    addAdmin: "添加管理员",
    adminWalletPlaceholder: "0x… 以太坊钱包地址",
    addAdminButton: "添加管理员",
    authorizedAdmins: "已授权管理员",
    authEnrolled: "✔ 身份验证器已启用",
    authPending: "⏳ 身份验证器待设置",
    activityLog: "操作历史与日志",
    filter: "筛选：",
    filterAll: "所有网络与状态",
    filterMainnet: "仅主网",
    filterTestnet: "仅测试网",
    filterPending: "仅待确认",
    filterConfirmed: "仅已确认",
    filterFailed: "仅失败",
    noActivity: "未找到操作记录。"
  }
};

const API = (url, options = {}) => fetch(url, { credentials: "same-origin", ...options }).then(async response => {
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw Error(data.error || `Request failed (${response.status})`);
  return data;
});

function shortAddress(value) {
  return value ? `${value.slice(0, 6)}…${value.slice(-4)}` : "";
}

function suggestedSymbol(name) {
  return (name || "").replace(/[^a-z0-9]/gi, "").toUpperCase().slice(0, 12);
}

export default function AdminApp() {
  // Language selection: defaults to "en", saved to localStorage
  const [lang, setLang] = useState(() => {
    try {
      return localStorage.getItem("admin_lang") || "en";
    } catch {
      return "en";
    }
  });

  const t = TRANSLATIONS[lang] || TRANSLATIONS.en;

  const changeLang = (newLang) => {
    setLang(newLang);
    try {
      localStorage.setItem("admin_lang", newLang);
    } catch {}
  };

  // Navigation & Auth
  const [phase, setPhase] = useState("login");
  const [ticket, setTicket] = useState(null);
  const [code, setCode] = useState("");
  const [message, setMessage] = useState("");
  const [user, setUser] = useState(null);
  const [qr, setQr] = useState(null);
  const [activeTab, setActiveTab] = useState("curve");

  // Shared Admin State & Network
  const [currentNetwork, setCurrentNetwork] = useState(null);
  const [chainId, setChainId] = useState(null);
  const [sharedDeployments, setSharedDeployments] = useState([]);
  const [sharedActivity, setSharedActivity] = useState([]);
  const [selectedDeploymentId, setSelectedDeploymentId] = useState("");
  const [actionStatus, setActionStatus] = useState("");

  // Deployment Form State
  const [deploymentLabel, setDeploymentLabel] = useState("");
  const [tokenSymbol, setTokenSymbol] = useState("");
  const [tokenSymbolCustom, setTokenSymbolCustom] = useState(false);
  const [deployTokenAddress, setDeployTokenAddress] = useState("");
  const [curveAddress, setCurveAddress] = useState("");
  const [liveEthUsd, setLiveEthUsd] = useState("");
  const [deployEthUsd, setDeployEthUsd] = useState("");
  const [curveEthUsd, setCurveEthUsd] = useState("");
  const [deploying, setDeploying] = useState(false);

  // Curve Live State
  const [curveState, setCurveState] = useState({
    indexUsd: "—",
    totalSold: "—",
    saleOpen: null,
    claimsOpen: null
  });

  // Treasury & Test Actions State
  const [withdrawAmount, setWithdrawAmount] = useState("0.001");
  const [buyAmount, setBuyAmount] = useState("0.001");

  // API Key Pool State
  const [keys, setKeys] = useState([]);
  const [dailyBudgets, setDailyBudgets] = useState([]);
  const [keyForm, setKeyForm] = useState({ provider: "", label: "production", secret: "", monthlyLimit: "", expiresAt: "" });

  // Administrators State
  const [adminsList, setAdminsList] = useState([]);
  const [newAdminAddress, setNewAdminAddress] = useState("");

  // Activity Filter State
  const [activityFilter, setActivityFilter] = useState("all");

  // Sync wallet & network
  const getWalletAndSigner = async () => {
    if (!window.ethereum) throw Error(t.walletExtensionRequired);
    const provider = new ethers.BrowserProvider(window.ethereum);
    const signer = await provider.getSigner();
    const net = await provider.getNetwork();
    const id = Number(net.chainId);
    const matched = Object.values(NETWORKS).find(item => item.id === id);
    setCurrentNetwork(matched || null);
    setChainId(id);
    return { provider, signer, network: matched };
  };

  const syncNetworkOnly = async () => {
    if (!window.ethereum) return;
    try {
      const provider = new ethers.BrowserProvider(window.ethereum);
      const net = await provider.getNetwork();
      const id = Number(net.chainId);
      const matched = Object.values(NETWORKS).find(item => item.id === id);
      setCurrentNetwork(matched || null);
      setChainId(id);
    } catch {}
  };

  const switchNetwork = async (kind) => {
    try {
      if (!window.ethereum) throw Error(t.walletExtensionRequired);
      const net = NETWORKS[kind];
      const hexId = `0x${net.id.toString(16)}`;
      try {
        await window.ethereum.request({ method: "wallet_switchEthereumChain", params: [{ chainId: hexId }] });
      } catch (err) {
        if (err.code === 4902) {
          await window.ethereum.request({
            method: "wallet_addEthereumChain",
            params: [{
              chainId: hexId,
              chainName: net.name,
              nativeCurrency: { name: "Ether", symbol: "ETH", decimals: 18 },
              rpcUrls: [net.rpc],
              blockExplorerUrls: [net.explorer]
            }]
          });
        } else {
          throw err;
        }
      }
      await getWalletAndSigner();
      await recordActivity("Network switched to " + net.name, "confirmed");
      setActionStatus(`Connected to ${net.name}`);
    } catch (err) {
      setActionStatus(err.shortMessage || err.message);
    }
  };

  // Data Loading
  const refreshSharedState = () => {
    API("/api/admin/state")
      .then(data => {
        setSharedDeployments(data.deployments || []);
        setSharedActivity(data.activity || []);
      })
      .catch(() => {});
  };

  const refreshApiKeys = () => {
    API("/api/admin/api-keys")
      .then(data => {
        setKeys(data.keys || []);
        setDailyBudgets(data.dailyBudgets || []);
      })
      .catch(err => setMessage(err.message));
  };

  const refreshAdmins = () => {
    API("/api/admins")
      .then(data => setAdminsList(data.admins || []))
      .catch(() => {});
  };

  const loadLiveRate = async () => {
    try {
      const res = await fetch("https://api.coinbase.com/v2/prices/ETH-USD/spot");
      const data = await res.json();
      const val = Number(data?.data?.amount);
      if (Number.isFinite(val) && val > 0) {
        const formatted = val.toFixed(2);
        setLiveEthUsd(formatted);
        setDeployEthUsd(prev => prev || formatted);
        setCurveEthUsd(prev => prev || formatted);
      }
    } catch {}
  };

  const recordActivity = async (action, state, hash = "", depId = "") => {
    try {
      const net = currentNetwork?.short || (chainId === 46630 ? "testnet" : "mainnet");
      await API("/api/admin/activity", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action, state, network: net, hash: hash || "", deploymentId: depId || selectedDeploymentId || "" })
      });
      refreshSharedState();
    } catch {}
  };

  // Curve Read State
  const refreshCurveState = async () => {
    if (!curveAddress) return;
    try {
      const { signer } = await getWalletAndSigner();
      const curveContract = new ethers.Contract(curveAddress, TEST_ADMIN_ARTIFACTS.curve.abi, signer);
      const [index, sold, sale, claims] = await Promise.all([
        curveContract.indexUsd(),
        curveContract.totalSold(),
        curveContract.saleOpen(),
        curveContract.claimsOpen()
      ]);
      setCurveState({
        indexUsd: `$${Number(ethers.formatUnits(index, 18)).toLocaleString()}`,
        totalSold: `${Number(ethers.formatUnits(sold, 18)).toLocaleString()} tokens`,
        saleOpen: sale,
        claimsOpen: claims
      });
    } catch (err) {
      setActionStatus(`Curve state check: ${err.shortMessage || err.message}`);
    }
  };

  // Lifecycle
  useEffect(() => {
    if (phase === "panel") {
      refreshSharedState();
      refreshApiKeys();
      refreshAdmins();
      loadLiveRate();
      syncNetworkOnly();
      const timer = setInterval(() => {
        refreshSharedState();
        refreshApiKeys();
      }, 10000);
      return () => clearInterval(timer);
    }
  }, [phase]);

  useEffect(() => {
    if (phase !== "enroll" || !ticket) return;
    API("/api/auth/totp-setup", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ticket })
    })
      .then(data => setQr(data.qrDataUrl))
      .catch(err => setMessage(err.message));
  }, [phase, ticket]);

  useEffect(() => {
    if (curveAddress) {
      refreshCurveState();
    }
  }, [curveAddress, currentNetwork]);

  // Auth Handlers
  const connect = async () => {
    try {
      if (!window.ethereum) throw Error(t.walletExtensionRequired);
      const provider = new ethers.BrowserProvider(window.ethereum);
      const signer = await provider.getSigner();
      const address = await signer.getAddress();
      const nonce = await API("/api/auth/nonce", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ address })
      });
      const signature = await signer.signMessage(nonce.message);
      const verified = await API("/api/auth/verify-wallet", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ challengeId: nonce.challengeId, signature })
      });
      setTicket(verified.ticket);
      setPhase(verified.phase);
      setMessage("");
    } catch (err) {
      setMessage(err.message);
    }
  };

  const verify = async () => {
    try {
      const data = await API("/api/auth/verify-totp", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ticket, code })
      });
      setUser(data);
      setPhase("panel");
      setMessage("");
    } catch (err) {
      setMessage(err.message);
    }
  };

  // Deployment Select Handler
  const selectDeployment = (id) => {
    if (!id) {
      clearDeployment();
      return;
    }
    const found = sharedDeployments.find(item => item.id === id);
    if (!found) return;
    setSelectedDeploymentId(found.id);
    setDeploymentLabel(found.label || "");
    setTokenSymbol(found.tokenSymbol || "");
    setTokenSymbolCustom(true);
    setDeployTokenAddress(found.tokenAddress || "");
    setCurveAddress(found.curveAddress || "");
    setActionStatus(t.savedDeploymentInfo.replace("{label}", found.label).replace("{network}", found.network));
  };

  const clearDeployment = () => {
    setSelectedDeploymentId("");
    setDeploymentLabel("");
    setTokenSymbol("");
    setTokenSymbolCustom(false);
    setDeployTokenAddress("");
    setCurveAddress("");
    setCurveState({ indexUsd: "—", totalSold: "—", saleOpen: null, claimsOpen: null });
    setActionStatus(t.readyNewDeployment);
  };

  const saveDeployment = async () => {
    try {
      if (!currentNetwork) throw Error("Select Robinhood Mainnet or Testnet first");
      if (!deployTokenAddress || !curveAddress) throw Error("Token and Curve addresses are required");
      const name = deploymentLabel.trim() || "Robinity Intelligence Deployment";
      const symbol = tokenSymbol.trim() || suggestedSymbol(name) || "TOKEN";
      const saved = await API("/api/admin/deployments", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          id: selectedDeploymentId || undefined,
          label: name,
          tokenSymbol: symbol,
          network: currentNetwork.short,
          tokenAddress: ethers.getAddress(deployTokenAddress),
          curveAddress: ethers.getAddress(curveAddress)
        })
      });
      setSelectedDeploymentId(saved.deployment?.id || "");
      await recordActivity("Deployment saved: " + name, "confirmed");
      setActionStatus(`Saved deployment "${name}"`);
      refreshSharedState();
    } catch (err) {
      setActionStatus(`Error: ${err.message}`);
    }
  };

  // Contract Deployment
  const deployStack = async () => {
    try {
      setActionStatus("");
      setDeploying(true);
      const { signer, network } = await getWalletAndSigner();
      if (!network) throw Error("Switch to Robinhood Chain Mainnet or Testnet before submitting a transaction");
      const name = deploymentLabel.trim();
      if (!name) throw Error("Enter a deployment and token name");
      const symbol = tokenSymbol.trim() || suggestedSymbol(name) || "TOKEN";
      setTokenSymbol(symbol);
      const ethPrice = deployEthUsd || liveEthUsd;
      if (!ethPrice) throw Error("ETH/USD price is required (load live rate or enter manually)");

      setActionStatus(`Deploying ${name} token…`);
      const tokenFactory = new ethers.ContractFactory(TEST_ADMIN_ARTIFACTS.token.abi, TEST_ADMIN_ARTIFACTS.token.bytecode, signer);
      const tokenContract = await tokenFactory.deploy(name, symbol);
      const tokenHash = tokenContract.deploymentTransaction().hash;
      await recordActivity(`Deploy ${name} token`, "pending", tokenHash);
      setActionStatus(`Token tx submitted: ${tokenHash}. Confirming on-chain…`);
      await tokenContract.waitForDeployment();
      const tokenAddr = await tokenContract.getAddress();
      setDeployTokenAddress(tokenAddr);
      await recordActivity(`Deploy ${name} token`, "confirmed", tokenHash);

      setActionStatus(`Deploying ${name}Curve…`);
      const curveFactory = new ethers.ContractFactory(TEST_ADMIN_ARTIFACTS.curve.abi, TEST_ADMIN_ARTIFACTS.curve.bytecode, signer);
      const curveContract = await curveFactory.deploy(ethers.parseUnits(ethPrice, 18), `${name}Curve`);
      const curveHash = curveContract.deploymentTransaction().hash;
      await recordActivity(`Deploy ${name}Curve`, "pending", curveHash);
      setActionStatus(`Curve tx submitted: ${curveHash}. Confirming on-chain…`);
      await curveContract.waitForDeployment();
      const curveAddr = await curveContract.getAddress();
      setCurveAddress(curveAddr);
      await recordActivity(`Deploy ${name}Curve`, "confirmed", curveHash);

      const saved = await API("/api/admin/deployments", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          label: name,
          tokenSymbol: symbol,
          network: network.short,
          tokenAddress: tokenAddr,
          curveAddress: curveAddr
        })
      });
      setSelectedDeploymentId(saved.deployment?.id || "");
      refreshSharedState();
      setActionStatus(`✔ Successfully deployed ${name} Token & ${name}Curve!`);
    } catch (err) {
      setActionStatus(`Deploy failed: ${err.shortMessage || err.message}`);
      recordActivity("Deploy contract stack", "failed");
    } finally {
      setDeploying(false);
    }
  };

  // Wire token & fund curve
  const wireToken = async () => {
    try {
      setActionStatus("");
      const { signer } = await getWalletAndSigner();
      if (!deployTokenAddress || !curveAddress) throw Error("Provide both token address and curve address");
      const curve = new ethers.Contract(curveAddress, TEST_ADMIN_ARTIFACTS.curve.abi, signer);
      const token = new ethers.Contract(deployTokenAddress, TEST_ADMIN_ARTIFACTS.token.abi, signer);

      setActionStatus("1/2: Setting token on curve contract…");
      const setTokenTx = await curve.setToken(deployTokenAddress);
      await recordActivity("Set curve token", "pending", setTokenTx.hash);
      await setTokenTx.wait();
      await recordActivity("Set curve token", "confirmed", setTokenTx.hash);

      setActionStatus("2/2: Funding curve with 200,000,000 tokens…");
      const fundTx = await token.transfer(curveAddress, ethers.parseUnits("200000000", 18));
      await recordActivity("Fund curve with 200M tokens", "pending", fundTx.hash);
      await fundTx.wait();
      await recordActivity("Fund curve with 200M tokens", "confirmed", fundTx.hash);

      setActionStatus("✔ Token set and curve funded with 200,000,000 tokens!");
      refreshCurveState();
    } catch (err) {
      setActionStatus(`Wiring failed: ${err.shortMessage || err.message}`);
      recordActivity("Set token and fund curve", "failed");
    }
  };

  // Curve Interactions
  const updateRate = async () => {
    try {
      setActionStatus("");
      const { signer } = await getWalletAndSigner();
      if (!curveAddress) throw Error("Curve address required");
      if (!curveEthUsd) throw Error("Enter ETH/USD rate");
      const curve = new ethers.Contract(curveAddress, TEST_ADMIN_ARTIFACTS.curve.abi, signer);
      const tx = await curve.setEthUsdWad(ethers.parseUnits(curveEthUsd, 18));
      await recordActivity("Update curve rate", "pending", tx.hash);
      setActionStatus(`Transaction sent: ${tx.hash}`);
      await tx.wait();
      await recordActivity("Update curve rate", "confirmed", tx.hash);
      setActionStatus("✔ Curve ETH/USD rate updated!");
      refreshCurveState();
    } catch (err) {
      setActionStatus(`Error: ${err.shortMessage || err.message}`);
      recordActivity("Update curve rate", "failed");
    }
  };

  const toggleSale = async () => {
    try {
      setActionStatus("");
      const { signer } = await getWalletAndSigner();
      if (!curveAddress) throw Error("Curve address required");
      const curve = new ethers.Contract(curveAddress, TEST_ADMIN_ARTIFACTS.curve.abi, signer);
      const current = await curve.saleOpen();
      const tx = await curve.setSaleOpen(!current);
      await recordActivity("Toggle sale to " + (!current ? "open" : "closed"), "pending", tx.hash);
      setActionStatus(`Transaction sent: ${tx.hash}`);
      await tx.wait();
      await recordActivity("Toggle sale to " + (!current ? "open" : "closed"), "confirmed", tx.hash);
      setActionStatus(`✔ Sale is now ${!current ? "OPEN" : "CLOSED"}`);
      refreshCurveState();
    } catch (err) {
      setActionStatus(`Error: ${err.shortMessage || err.message}`);
      recordActivity("Toggle sale", "failed");
    }
  };

  const toggleClaims = async () => {
    try {
      setActionStatus("");
      const { signer } = await getWalletAndSigner();
      if (!curveAddress) throw Error("Curve address required");
      const curve = new ethers.Contract(curveAddress, TEST_ADMIN_ARTIFACTS.curve.abi, signer);
      const current = await curve.claimsOpen();
      const tx = await curve.setClaimsOpen(!current);
      await recordActivity("Toggle claims to " + (!current ? "open" : "closed"), "pending", tx.hash);
      setActionStatus(`Transaction sent: ${tx.hash}`);
      await tx.wait();
      await recordActivity("Toggle claims to " + (!current ? "open" : "closed"), "confirmed", tx.hash);
      setActionStatus(`✔ Claims are now ${!current ? "OPEN" : "CLOSED"}`);
      refreshCurveState();
    } catch (err) {
      setActionStatus(`Error: ${err.shortMessage || err.message}`);
      recordActivity("Toggle claims", "failed");
    }
  };

  const handleWithdraw = async (percentage99 = false) => {
    try {
      setActionStatus("");
      const { provider, signer } = await getWalletAndSigner();
      if (!curveAddress) throw Error("Curve address required");
      const curve = new ethers.Contract(curveAddress, TEST_ADMIN_ARTIFACTS.curve.abi, signer);
      let tx;
      if (percentage99) {
        const balance = await provider.getBalance(curveAddress);
        if (balance <= 0n) throw Error("Curve has zero ETH balance");
        const amount = (balance * 99n) / 100n;
        tx = await curve.withdraw(amount);
      } else {
        if (!withdrawAmount) throw Error("Enter withdraw amount in ETH");
        tx = await curve.withdraw(ethers.parseEther(withdrawAmount));
      }
      await recordActivity("Treasury withdrawal", "pending", tx.hash);
      setActionStatus(`Withdraw tx sent: ${tx.hash}`);
      await tx.wait();
      await recordActivity("Treasury withdrawal", "confirmed", tx.hash);
      setActionStatus("✔ Treasury withdrawal confirmed!");
    } catch (err) {
      setActionStatus(`Withdraw failed: ${err.shortMessage || err.message}`);
      recordActivity("Treasury withdrawal", "failed");
    }
  };

  const handleBuy = async () => {
    try {
      setActionStatus("");
      const { signer } = await getWalletAndSigner();
      if (!curveAddress) throw Error("Curve address required");
      if (!buyAmount) throw Error("Enter buy amount in ETH");
      const curve = new ethers.Contract(curveAddress, TEST_ADMIN_ARTIFACTS.curve.abi, signer);
      const tx = await curve.buy({ value: ethers.parseEther(buyAmount) });
      await recordActivity("Buy token", "pending", tx.hash);
      setActionStatus(`Buy tx sent: ${tx.hash}`);
      await tx.wait();
      await recordActivity("Buy token", "confirmed", tx.hash);
      setActionStatus("✔ Token purchase successful!");
      refreshCurveState();
    } catch (err) {
      setActionStatus(`Buy failed: ${err.shortMessage || err.message}`);
      recordActivity("Buy token", "failed");
    }
  };

  const handleClaim = async () => {
    try {
      setActionStatus("");
      const { signer } = await getWalletAndSigner();
      if (!curveAddress) throw Error("Curve address required");
      const curve = new ethers.Contract(curveAddress, TEST_ADMIN_ARTIFACTS.curve.abi, signer);
      const tx = await curve.claim();
      await recordActivity("Claim token", "pending", tx.hash);
      setActionStatus(`Claim tx sent: ${tx.hash}`);
      await tx.wait();
      await recordActivity("Claim token", "confirmed", tx.hash);
      setActionStatus("✔ Tokens successfully claimed!");
      refreshCurveState();
    } catch (err) {
      setActionStatus(`Claim failed: ${err.shortMessage || err.message}`);
      recordActivity("Claim token", "failed");
    }
  };

  // API Key Pool Actions
  const addApiKey = async (e) => {
    e.preventDefault();
    try {
      await API("/api/admin/api-keys", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ...keyForm, monthlyLimit: Number(keyForm.monthlyLimit || 0) })
      });
      setKeyForm({ provider: "", label: "production", secret: "", monthlyLimit: "", expiresAt: "" });
      setMessage("Encrypted API key stored in vault and pool updated.");
      refreshApiKeys();
    } catch (err) {
      setMessage(err.message);
    }
  };

  const apiKeyAction = async (action, keyId) => {
    try {
      if (action === "delete") {
        if (!confirm(t.confirmDeleteKey)) return;
        await API(`/api/admin/api-keys/${encodeURIComponent(keyId)}`, { method: "DELETE" });
      } else if (action === "rotate") {
        const secret = prompt(t.rotatePrompt);
        if (!secret) return;
        await API("/api/admin/api-keys/rotate", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ id: keyId, secret })
        });
      } else if (action === "toggle") {
        await API("/api/admin/api-keys/toggle", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ id: keyId })
        });
      }
      refreshApiKeys();
    } catch (err) {
      setMessage(err.message);
    }
  };

  // Admins Actions
  const addAdmin = async (e) => {
    e.preventDefault();
    try {
      await API("/api/admins", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ address: newAdminAddress })
      });
      setNewAdminAddress("");
      setMessage(`Added admin ${newAdminAddress}`);
      await recordActivity("Administrator added", "confirmed");
      refreshAdmins();
    } catch (err) {
      setMessage(err.message);
    }
  };

  // Filtered activity
  const filteredActivity = sharedActivity.filter(item => {
    if (activityFilter === "all") return true;
    if (activityFilter === "mainnet" || activityFilter === "testnet") return item.network === activityFilter;
    if (activityFilter === "pending" || activityFilter === "confirmed" || activityFilter === "failed") return item.state === activityFilter;
    return true;
  });

  // Login / Auth Views
  if (phase !== "panel") {
    return (
      <>
        <PublicHeader legal />
        <main className="auth-card">
          <div className="eyebrow">{t.protectedWorkspace}</div>
          <h1>{phase === "enroll" ? t.setUpAuth : phase === "totp" ? t.enterAuthCode : t.adminAccess}</h1>
          {phase === "login" ? (
            <button className="button" onClick={connect}>{t.connectWallet}</button>
          ) : (
            <>
              {phase === "enroll" && (
                qr ? <img className="admin-qr" src={qr} alt="Authenticator setup QR code" style={{ display: "block", width: 220, margin: "16px auto", borderRadius: 10 }} /> : <p className="muted">{t.preparingAuth}</p>
              )}
              <p className="muted">{phase === "enroll" ? t.scanQrNotice : t.enterCodeNotice}</p>
              <input
                className="amount-input"
                inputMode="numeric"
                maxLength="6"
                value={code}
                onChange={e => setCode(e.target.value.replace(/\D/g, "").slice(0, 6))}
                placeholder="000000"
              />
              <button className="button" onClick={verify}>{t.verify}</button>
            </>
          )}
          <p className="error" role="alert">{message}</p>
        </main>
        <PublicFooter />
      </>
    );
  }

  // Admin Dashboard View
  const networkDeployments = currentNetwork ? sharedDeployments.filter(d => d.network === currentNetwork.short) : sharedDeployments;

  return (
    <>
      <PublicHeader legal />
      <main className="admin-main">
        {/* Top bar with identity, language switch and refresh */}
        <div className="admin-heading">
          <div>
            <div className="eyebrow">{t.subtitle}</div>
            <h1>{t.title}</h1>
            <p className="muted">{shortAddress(user?.address)} · {user?.role}</p>
          </div>
          <div style={{ display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap" }}>
            <div className="lang-selector-box">
              <span>🌐</span>
              <select value={lang} onChange={e => changeLang(e.target.value)} className="lang-select">
                <option value="en">English (Default)</option>
                <option value="tr">Türkçe</option>
                <option value="zh">简体中文</option>
              </select>
            </div>
            <button className="button secondary" onClick={() => { refreshSharedState(); refreshApiKeys(); refreshAdmins(); }}>
              {t.refreshAll}
            </button>
          </div>
        </div>

        {/* Network status bar */}
        <div className="network-bar">
          <div className="network-info">
            <span className="muted">{t.activeNetwork}</span>
            <span className={`network-badge ${currentNetwork ? "connected" : ""}`}>
              {currentNetwork ? `${currentNetwork.name} (${currentNetwork.id})` : chainId ? `Chain ID ${chainId} (${t.unsupported})` : t.walletNotConnected}
            </span>
          </div>
          <div className="network-actions">
            <button className="button secondary" onClick={() => switchNetwork("testnet")}>
              {t.switchTestnet}
            </button>
            <button className="button secondary" onClick={() => switchNetwork("mainnet")}>
              {t.switchMainnet}
            </button>
          </div>
        </div>

        {/* Tabs Navigation */}
        <div className="admin-tabs">
          <button className={`admin-tab ${activeTab === "curve" ? "active" : ""}`} onClick={() => setActiveTab("curve")}>
            {t.tabCurve}
          </button>
          <button className={`admin-tab ${activeTab === "api" ? "active" : ""}`} onClick={() => setActiveTab("api")}>
            {t.tabApi} ({keys.length})
          </button>
          <button className={`admin-tab ${activeTab === "admins" ? "active" : ""}`} onClick={() => setActiveTab("admins")}>
            {t.tabAdmins} ({adminsList.length})
          </button>
          <button className={`admin-tab ${activeTab === "activity" ? "active" : ""}`} onClick={() => setActiveTab("activity")}>
            {t.tabActivity} ({sharedActivity.length})
          </button>
        </div>

        {/* Action Status Banner */}
        {actionStatus && <div className="action-banner">{actionStatus}</div>}
        {message && <p className="error" role="alert">{message}</p>}

        {/* TAB 1: CURVE & DEPLOY MANAGEMENT */}
        {activeTab === "curve" && (
          <div className="admin-grid">
            {/* Deployment Selector Card */}
            <section className="admin-panel wide">
              <h2>
                <span>{t.deploymentSelection}</span>
                <button className="button secondary" style={{ minHeight: 34, padding: "0 12px", fontSize: 11 }} onClick={clearDeployment}>
                  {t.newDeployment}
                </button>
              </h2>
              <div className="row">
                <div>
                  <label>{t.deploymentSelection}</label>
                  <select value={selectedDeploymentId} onChange={e => selectDeployment(e.target.value)}>
                    <option value="">{t.selectDeploymentPlaceholder}</option>
                    {networkDeployments.map(d => (
                      <option key={d.id} value={d.id}>
                        {d.label} ({d.tokenSymbol || "TOKEN"}) · {d.network}
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <label>{t.deploymentLabel}</label>
                  <input
                    placeholder={t.deploymentLabelPlaceholder}
                    value={deploymentLabel}
                    onChange={e => {
                      setDeploymentLabel(e.target.value);
                      if (!tokenSymbolCustom) setTokenSymbol(suggestedSymbol(e.target.value));
                    }}
                  />
                </div>
              </div>
              <div className="row" style={{ marginTop: 8 }}>
                <div>
                  <label>{t.tokenSymbol}</label>
                  <input
                    placeholder={t.tokenSymbolPlaceholder}
                    value={tokenSymbol}
                    onChange={e => {
                      setTokenSymbol(e.target.value);
                      setTokenSymbolCustom(true);
                    }}
                  />
                </div>
                <div style={{ display: "flex", alignItems: "flex-end" }}>
                  <button className="button secondary" style={{ width: "100%" }} onClick={saveDeployment}>
                    {t.saveAddresses}
                  </button>
                </div>
              </div>
            </section>

            {/* Deploy Contracts Card */}
            <section className="admin-panel">
              <h2>{t.deployContracts}</h2>
              <label>{t.liveEthUsd}</label>
              <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
                <input readOnly value={liveEthUsd ? `1 ETH = $${liveEthUsd}` : t.priceLoading} style={{ background: "rgba(143,170,196,0.06)" }} />
                <button className="button secondary" style={{ width: "auto", whiteSpace: "nowrap" }} onClick={() => { loadLiveRate(); setDeployEthUsd(liveEthUsd); }}>
                  {t.useLivePrice}
                </button>
              </div>

              <label>{t.initialEthUsd}</label>
              <input
                inputMode="decimal"
                placeholder={t.initialEthUsdPlaceholder}
                value={deployEthUsd}
                onChange={e => setDeployEthUsd(e.target.value)}
              />

              <div style={{ marginTop: 14 }}>
                <button className="button" style={{ width: "100%" }} disabled={deploying} onClick={deployStack}>
                  {deploying ? t.deploying : deploymentLabel ? t.deployButtonNamed.replace("{name}", deploymentLabel) : t.deployButton}
                </button>
              </div>

              <label>{t.activeTokenAddress}</label>
              <input
                placeholder={t.tokenAddressPlaceholder}
                value={deployTokenAddress}
                onChange={e => setDeployTokenAddress(e.target.value)}
              />

              <label>{t.activeCurveAddress}</label>
              <input
                placeholder={t.curveAddressPlaceholder}
                value={curveAddress}
                onChange={e => setCurveAddress(e.target.value)}
              />

              <div style={{ marginTop: 14 }}>
                <button className="button secondary" style={{ width: "100%" }} onClick={wireToken}>
                  {t.wireAndFund}
                </button>
              </div>
            </section>

            {/* Curve Management Card */}
            <section className="admin-panel">
              <h2>
                <span>{t.liveCurveStatus}</span>
                <button className="button secondary" style={{ minHeight: 32, padding: "0 10px", fontSize: 11 }} onClick={refreshCurveState}>
                  {t.refresh}
                </button>
              </h2>

              <div className="curve-metrics-row">
                <div className="metric-box">
                  <span>{t.incomingFunds}</span>
                  <b>{curveState.indexUsd}</b>
                </div>
                <div className="metric-box">
                  <span>{t.tokensSold}</span>
                  <b>{curveState.totalSold}</b>
                </div>
                <div className="metric-box">
                  <span>{t.saleStatus}</span>
                  <div style={{ marginTop: 6 }}>
                    <span className={`status-pill ${curveState.saleOpen ? "open" : "closed"}`}>
                      {curveState.saleOpen === null ? "—" : curveState.saleOpen ? t.open : t.closed}
                    </span>
                  </div>
                </div>
                <div className="metric-box">
                  <span>{t.claimsStatus}</span>
                  <div style={{ marginTop: 6 }}>
                    <span className={`status-pill ${curveState.claimsOpen ? "open" : "closed"}`}>
                      {curveState.claimsOpen === null ? "—" : curveState.claimsOpen ? t.open : t.closed}
                    </span>
                  </div>
                </div>
              </div>

              <label>{t.curveEthUsdRate}</label>
              <div style={{ display: "flex", gap: 8 }}>
                <input
                  inputMode="decimal"
                  placeholder="2500"
                  value={curveEthUsd}
                  onChange={e => setCurveEthUsd(e.target.value)}
                />
                <button className="button secondary" style={{ width: "auto", whiteSpace: "nowrap" }} onClick={updateRate}>
                  {t.updateRate}
                </button>
              </div>

              <div className="row" style={{ marginTop: 14 }}>
                <button className="button secondary" onClick={toggleSale}>
                  {curveState.saleOpen ? t.closeSale : t.openSale}
                </button>
                <button className="button secondary" onClick={toggleClaims}>
                  {curveState.claimsOpen ? t.closeClaims : t.openClaims}
                </button>
              </div>
            </section>

            {/* Treasury Card */}
            <section className="admin-panel">
              <h2>{t.treasuryActions}</h2>
              <label>{t.withdrawAmountEth}</label>
              <input
                inputMode="decimal"
                value={withdrawAmount}
                onChange={e => setWithdrawAmount(e.target.value)}
              />
              <div className="row" style={{ marginTop: 14 }}>
                <button className="button secondary" onClick={() => handleWithdraw(false)}>
                  {t.withdraw}
                </button>
                <button className="button secondary" style={{ color: "var(--ds-orange)" }} onClick={() => handleWithdraw(true)}>
                  {t.withdraw99}
                </button>
              </div>
              <p className="muted" style={{ fontSize: 11, marginTop: 10 }}>
                {t.treasuryNotice}
              </p>
            </section>

            {/* Test Actions Card */}
            <section className="admin-panel">
              <h2>{t.testActions}</h2>
              <label>{t.buyAmountEth}</label>
              <input
                inputMode="decimal"
                value={buyAmount}
                onChange={e => setBuyAmount(e.target.value)}
              />
              <div className="row" style={{ marginTop: 14 }}>
                <button className="button" onClick={handleBuy}>
                  {t.buyTokens}
                </button>
                <button className="button secondary" onClick={handleClaim}>
                  {t.claimTokens}
                </button>
              </div>
              <p className="muted" style={{ fontSize: 11, marginTop: 10 }}>
                {t.testNotice}
              </p>
            </section>
          </div>
        )}

        {/* TAB 2: API KEY POOL */}
        {activeTab === "api" && (
          <div>
            <ApiMonitor keys={keys} dailyBudgets={dailyBudgets} owner={user?.role === "owner"} refresh={refreshApiKeys} action={apiKeyAction} saveSettings={settings => API("/api/admin/api-keys/settings", {method:"POST", body: JSON.stringify(settings)})} />

            {user?.role === "owner" && (
              <section className="admin-panel" style={{ marginTop: 20 }}>
                <h2>{t.addApiKey}</h2>
                <p className="muted">GoPlus accepts an access token here. App key / secret pairs are configured on the server. Monthly limits are local request budgets, not provider credit balances.</p>
                <form onSubmit={addApiKey} className="key-form">
                  <select
                    aria-label="API provider"
                    required
                    value={keyForm.provider}
                    onChange={e => setKeyForm({ ...keyForm, provider: e.target.value })}
                  ><option value="">Select provider</option>{['GoPlus', 'Helius', 'Etherscan', 'Bitquery'].map(provider => <option key={provider}>{provider}</option>)}</select>
                  <input
                    placeholder={t.labelPlaceholder}
                    value={keyForm.label}
                    onChange={e => setKeyForm({ ...keyForm, label: e.target.value })}
                  />
                  <input
                    type="password"
                    placeholder={t.secretPlaceholder}
                    value={keyForm.secret}
                    onChange={e => setKeyForm({ ...keyForm, secret: e.target.value })}
                  />
                  <input
                    type="number"
                    placeholder={t.monthlyLimitPlaceholder}
                    value={keyForm.monthlyLimit}
                    onChange={e => setKeyForm({ ...keyForm, monthlyLimit: e.target.value })}
                  />
                  <input
                    type="date"
                    placeholder={t.expiresPlaceholder}
                    value={keyForm.expiresAt}
                    onChange={e => setKeyForm({ ...keyForm, expiresAt: e.target.value })}
                  />
                  <button className="button" type="submit">
                    {t.storeEncryptedKey}
                  </button>
                </form>
              </section>
            )}
          </div>
        )}

        {/* TAB 3: ADMINISTRATORS */}
        {activeTab === "admins" && (
          <div>
            {user?.role === "owner" && (
              <section className="admin-panel">
                <h2>{t.addAdmin}</h2>
                <form onSubmit={addAdmin} style={{ display: "flex", gap: 10 }}>
                  <input
                    placeholder={t.adminWalletPlaceholder}
                    value={newAdminAddress}
                    onChange={e => setNewAdminAddress(e.target.value)}
                  />
                  <button className="button" style={{ width: "auto", whiteSpace: "nowrap" }} type="submit">
                    {t.addAdminButton}
                  </button>
                </form>
              </section>
            )}

            <section className="admin-panel" style={{ marginTop: 20 }}>
              <h2>{t.authorizedAdmins}</h2>
              <ul className="activity-list" style={{ marginTop: 10 }}>
                {adminsList.map(a => (
                  <li key={a.address}>
                    <span style={{ fontWeight: 600 }}>{shortAddress(a.address)}</span>
                    <span className={`status-pill ${a.role === "owner" ? "active" : "pending"}`}>{a.role}</span>
                    <span>{a.authenticatorEnrolled ? t.authEnrolled : t.authPending}</span>
                  </li>
                ))}
              </ul>
            </section>
          </div>
        )}

        {/* TAB 4: ACTIVITY LOG */}
        {activeTab === "activity" && (
          <section className="admin-panel">
            <h2>
              <span>{t.activityLog}</span>
              <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
                <span className="muted" style={{ fontSize: 11 }}>{t.filter}</span>
                <select style={{ minHeight: 32, padding: "4px 8px", fontSize: 11, width: "auto" }} value={activityFilter} onChange={e => setActivityFilter(e.target.value)}>
                  <option value="all">{t.filterAll}</option>
                  <option value="mainnet">{t.filterMainnet}</option>
                  <option value="testnet">{t.filterTestnet}</option>
                  <option value="pending">{t.filterPending}</option>
                  <option value="confirmed">{t.filterConfirmed}</option>
                  <option value="failed">{t.filterFailed}</option>
                </select>
              </div>
            </h2>

            <ul className="activity-list">
              {filteredActivity.map(item => (
                <li key={item.id}>
                  <span className="muted">{new Date(item.at).toLocaleTimeString()} · {new Date(item.at).toLocaleDateString()}</span>
                  <div>
                    <span className={`status-pill ${item.state}`}>{item.network} · {item.state}</span>
                  </div>
                  <div>
                    <b>{item.action}</b>
                    {item.hash && (
                      <span style={{ display: "block", color: "var(--ds-muted)", fontSize: 11 }}>
                        Tx: {item.hash.slice(0, 18)}…{item.hash.slice(-8)}
                      </span>
                    )}
                  </div>
                </li>
              ))}
              {!filteredActivity.length && <p className="muted" style={{ padding: 20 }}>{t.noActivity}</p>}
            </ul>
          </section>
        )}
      </main>
      <PublicFooter />
    </>
  );
}
