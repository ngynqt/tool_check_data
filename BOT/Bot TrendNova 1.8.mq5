//+------------------------------------------------------------------+
//|                                     TrenNova_Pro_Complete_EA.mq5 |
//|   Tích hợp: Market + Risk/Fixed Lot + Dynamic Orders + Trailing  |
//|   Thuật toán lõi: Chống Repaint tuyệt đối (Array Loop 100 nến)   |
//+------------------------------------------------------------------+
#property strict
#include <Trade\Trade.mqh>

CTrade trade; // Khởi tạo class giao dịch

//--- Khai báo Danh sách chọn chế độ Lot
enum ENUM_LOT_MODE {
   LOT_AUTO_RISK,  // Tự động tính Lot theo % Vốn
   LOT_FIXED_MANUAL// Nhập Tổng Lot cố định thủ công
};

//--- Input Parameters
input group "=== RISK MANAGEMENT & DYNAMIC TP ==="
input ENUM_LOT_MODE InpLotMode      = LOT_AUTO_RISK; // Chế độ Quản lý Vốn
input double        InpRiskPercent  = 5.0;           // Tổng % Rủi ro (Nếu chọn Auto)
input double        InpFixedLot     = 0.03;          // Tổng Lot thủ công (Nếu chọn Fixed)
input int           InpOrderCount   = 3;             // Số lệnh muốn mở (1, 2, hoặc 3 lệnh)
input double        InpRiskFactor   = 3.0;           // Hệ số Stoploss ATR (VD: 3.0)
input int           InpMagicNum     = 888999;

input group "=== TRENNOVA INDICATOR ==="
input ENUM_TIMEFRAMES InpTrenNovaTimeFrame = PERIOD_CURRENT; // Khung thời gian của Chỉ báo
input double   InpSensitivity = 4.0;         // Supertrend Sensitivity
input int      InpATRPeriod   = 11;          // Supertrend ATR Period
input int      InpSMA_Filter  = 13;          // Trend Filter SMA

input group "=== HIGHER TIMEFRAME TREND FILTER ==="
input bool            InpUseTrendFilter      = true;      // Bật/Tắt lọc MA Xu Hướng
input int             MA_Trend_Period        = 200;       // Chu kỳ MA 
input ENUM_TIMEFRAMES TimeFrame_ConfirmMA    = PERIOD_H1; // Khung thời gian xét MA
input bool            TRADETHUANXUHUONG      = true;      // Cho phép đánh THUẬN xu hướng
input bool            TRADENGUOCXUHUONG      = false;     // Cho phép đánh NGƯỢC xu hướng

input group "=== DYNAMIC TRAILING STOP ==="
input bool     UseTrailingStop       = true;  // Bật Trailing Stop
input int      Trail_Start_Points    = 200;   // Mức LÃI kích hoạt dời SL (Points)
input int      Trail_Distance_Points = 100;   // Khoảng cách bám đuôi giá (Points)
input int      Trail_Step_Points     = 20;    // Bước nhảy tối thiểu để dời (Points)

input group "=== BREAK-EVEN SETTINGS ==="
input bool InpMoveBE = true; // Bật tự động dời SL về Hòa Vốn khi chạm TP1

input group "=== TRADING DIRECTION CONTROL ==="
input bool InpAllowHedging = false; // Bật/Tắt chế độ đánh nhiều cụm lệnh
// false = Tối đa 1 cụm lệnh trên biểu đồ (Đang có Buy thì cấm Sell và cấm nhồi thêm Buy)
// true  = Tối đa 1 cụm Buy và 1 cụm Sell cùng lúc (Được phép Hedging 2 đầu)

input group "=== TRADING TIME FILTER (KHUNG GIỜ) ==="
input bool   InpUseTimeFilter = true;       // Bật/Tắt giao dịch theo khung giờ
input string InpStartTime     = "14:00";    // Giờ bắt đầu (Mặc định: Đầu phiên Âu)
input string InpEndTime       = "23:00";    // Giờ kết thúc (Mặc định: Cuối phiên Mỹ)

//--- Global Variables
int            handleSMA, handleATR, handleMA_Trend;
datetime       lastBarTime;
double         prevUpBand = 0, prevDnBand = 0;
int            trendDirection = 1;

//+------------------------------------------------------------------+
//| Expert initialization function                                   |
//+------------------------------------------------------------------+
int OnInit()
{
   handleSMA = iMA(_Symbol, InpTrenNovaTimeFrame, InpSMA_Filter, 0, MODE_SMA, PRICE_CLOSE);
   handleATR = iATR(_Symbol, InpTrenNovaTimeFrame, InpATRPeriod);
   
   if(InpUseTrendFilter) {
      handleMA_Trend = iMA(_Symbol, TimeFrame_ConfirmMA, MA_Trend_Period, 0, MODE_SMA, PRICE_CLOSE);
      if(handleMA_Trend == INVALID_HANDLE) { Print("❌ Lỗi tải MA Trend Filter!"); return INIT_FAILED; }
   }
   
   if(handleSMA == INVALID_HANDLE || handleATR == INVALID_HANDLE) {
      Print("❌ Lỗi tải Indicator!");
      return INIT_FAILED;
   }
   
   trade.SetExpertMagicNumber(InpMagicNum);
   return INIT_SUCCEEDED;
}

//+------------------------------------------------------------------+
//| Hàm Kiểm Tra Khung Giờ Giao Dịch                                 |
//+------------------------------------------------------------------+
bool IsTradingTime()
{
   if(!InpUseTimeFilter) return true;

   string startArr[], endArr[];
   StringSplit(InpStartTime, ':', startArr);
   StringSplit(InpEndTime, ':', endArr);
   
   if(ArraySize(startArr) < 2 || ArraySize(endArr) < 2) return true;
   
   int start_mins = (int)StringToInteger(startArr[0]) * 60 + (int)StringToInteger(startArr[1]);
   int end_mins   = (int)StringToInteger(endArr[0]) * 60 + (int)StringToInteger(endArr[1]);
   
   MqlDateTime dt;
   TimeCurrent(dt);
   int current_mins = dt.hour * 60 + dt.min;
   
   if(start_mins < end_mins) {
      return (current_mins >= start_mins && current_mins <= end_mins);
   } else {
      return (current_mins >= start_mins || current_mins <= end_mins);
   }
}

//+------------------------------------------------------------------+
//| Main Trading Logic                                               |
//+------------------------------------------------------------------+
void OnTick()
{
   // ======================================================================
   // CƠ CHẾ TRAILING & BREAK-EVEN (Chạy liên tục mỗi tick)
   // ======================================================================
   if(InpMoveBE) CheckBreakEven();
   if(UseTrailingStop) HandleTrailingStop();

   // ======================================================================
   // BƯỚC 1: KIỂM TRA NẾN MỚI (CHỐNG REPAINT)
   // ======================================================================
   datetime current_time = iTime(_Symbol, InpTrenNovaTimeFrame, 0);
   if(current_time == lastBarTime) return; // Chỉ chạy 1 lần khi mở nến mới

   // ======================================================================
   // BƯỚC 2: TẢI DỮ LIỆU QUÁ KHỨ VÀO MẢNG (100 NẾN)
   // ======================================================================
   double close[], high[], low[], sma[], atr[];
   ArraySetAsSeries(close, true);
   ArraySetAsSeries(high, true);
   ArraySetAsSeries(low, true);
   ArraySetAsSeries(sma, true);
   ArraySetAsSeries(atr, true);

   int limit = 100; // Quét 100 nến để đảm bảo SuperTrend hội tụ chính xác
   if(CopyClose(_Symbol, InpTrenNovaTimeFrame, 0, limit, close) <= 0) return;
   if(CopyHigh(_Symbol, InpTrenNovaTimeFrame, 0, limit, high) <= 0) return;
   if(CopyLow(_Symbol, InpTrenNovaTimeFrame, 0, limit, low) <= 0) return;
   
   // Thay thế bằng các handle chuẩn của hệ thống Pro
   if(CopyBuffer(handleSMA, 0, 0, limit, sma) <= 0) return;
   if(CopyBuffer(handleATR, 0, 0, limit, atr) <= 0) return;

   // ======================================================================
   // BƯỚC 3: THUẬT TOÁN TÍNH SUPERTREND AN TOÀN (VÒNG LẶP NỘI BỘ)
   // ======================================================================
   double st_upper[], st_lower[], supertrend[];
   int st_dir[];
   ArrayResize(st_upper, limit);
   ArrayResize(st_lower, limit);
   ArrayResize(supertrend, limit);
   ArrayResize(st_dir, limit);
   
   ArraySetAsSeries(st_upper, true);
   ArraySetAsSeries(st_lower, true);
   ArraySetAsSeries(supertrend, true);
   ArraySetAsSeries(st_dir, true);

   // Khởi tạo mốc ban đầu (Nến cũ nhất)
   st_upper[limit-1] = close[limit-1] + InpSensitivity * atr[limit-1];
   st_lower[limit-1] = close[limit-1] - InpSensitivity * atr[limit-1];
   supertrend[limit-1] = st_upper[limit-1];
   st_dir[limit-1] = 1;

   // Lặp từ nến cũ nhất tiến dần về nến hiện tại
   for(int i = limit - 2; i >= 1; i--)
   {
      // Sử dụng Giá Đóng Cửa (Close) theo đúng nguyên bản TradingView
      double basic_upper = close[i] + InpSensitivity * atr[i];
      double basic_lower = close[i] - InpSensitivity * atr[i];
      
      // Logic ghim dải băng dưới
      if(basic_lower > st_lower[i+1] || close[i+1] < st_lower[i+1])
         st_lower[i] = basic_lower;
      else
         st_lower[i] = st_lower[i+1];
         
      // Logic ghim dải băng trên
      if(basic_upper < st_upper[i+1] || close[i+1] > st_upper[i+1])
         st_upper[i] = basic_upper;
      else
         st_upper[i] = st_upper[i+1];
         
      // Xác định xu hướng
      if(supertrend[i+1] == st_upper[i+1])
         st_dir[i] = (close[i] > st_upper[i]) ? -1 : 1;
      else
         st_dir[i] = (close[i] < st_lower[i]) ? 1 : -1;
         
      // Chốt giá trị SuperTrend
      supertrend[i] = (st_dir[i] == -1) ? st_lower[i] : st_upper[i];
   }

   // ======================================================================
   // BƯỚC 4: XUẤT TÍN HIỆU CUỐI CÙNG
   // ======================================================================
   // BUY: Giá đóng cửa cắt lên SuperTrend VÀ lớn hơn SMA13
   bool bull_cross = (close[1] > supertrend[1] && close[2] <= supertrend[2]);
   bool is_bull    = bull_cross && (close[1] >= sma[1]);

   // SELL: Giá đóng cửa cắt xuống SuperTrend VÀ nhỏ hơn SMA13
   bool bear_cross = (close[1] < supertrend[1] && close[2] >= supertrend[2]);
   bool is_bear    = bear_cross && (close[1] <= sma[1]);

   // Lưu thời gian nến để tránh tính toán lại
   lastBarTime = current_time; 

   // ==========================================================
   // BƯỚC 5: LOGIC XUỐNG LỆNH CỦA HỆ THỐNG PRO
   // ==========================================================
   bool hasBuy = HasBuyPosition();
   bool hasSell = HasSellPosition();

   bool canBuy = is_bull;
   bool canSell = is_bear;

   if(hasBuy) canBuy = false;
   if(hasSell) canSell = false;

   if(!InpAllowHedging) {
      if(hasBuy || hasSell) { canBuy = false; canSell = false; }
   }

   if(!IsTradingTime()) { canBuy = false; canSell = false; }

   if(InpUseTrendFilter && (canBuy || canSell)) 
   {
      double maTrendArray[1];
      if(CopyBuffer(handleMA_Trend, 0, 1, 1, maTrendArray) > 0) 
      {
         double maTrend = maTrendArray[0];
         bool isUptrend = (close[1] > maTrend);
         bool isDowntrend = (close[1] < maTrend);

         if(isUptrend) {
            if(!TRADETHUANXUHUONG) canBuy = false;  
            if(!TRADENGUOCXUHUONG) canSell = false; 
         }
         else if(isDowntrend) {
            if(!TRADETHUANXUHUONG) canSell = false; 
            if(!TRADENGUOCXUHUONG) canBuy = false;  
         }
      }
   }

   if(canBuy || canSell) 
   {
      double atrBand = atr[1] * InpRiskFactor;
      double entryPrice = SymbolInfoDouble(_Symbol, SYMBOL_ASK); 
      
      if(canBuy) 
      {
         double sl_buy = NormalizeDouble(low[1] - atrBand, _Digits);
         double risk_buy = entryPrice - sl_buy;
         
         if(risk_buy > 0) {
            double tp1 = NormalizeDouble(entryPrice + (risk_buy * 1.0), _Digits);
            double tp2 = NormalizeDouble(entryPrice + (risk_buy * 2.0), _Digits);
            double tp3 = NormalizeDouble(entryPrice + (risk_buy * 3.0), _Digits);
            ExecuteDynamicMarketEntry(ORDER_TYPE_BUY, sl_buy, tp1, tp2, tp3);
         }
      }
      else if(canSell) 
      {
         entryPrice = SymbolInfoDouble(_Symbol, SYMBOL_BID);
         double sl_sell = NormalizeDouble(high[1] + atrBand, _Digits);
         double risk_sell = sl_sell - entryPrice;
         
         if(risk_sell > 0) {
            double tp1 = NormalizeDouble(entryPrice - (risk_sell * 1.0), _Digits);
            double tp2 = NormalizeDouble(entryPrice - (risk_sell * 2.0), _Digits);
            double tp3 = NormalizeDouble(entryPrice - (risk_sell * 3.0), _Digits);
            ExecuteDynamicMarketEntry(ORDER_TYPE_SELL, sl_sell, tp1, tp2, tp3);
         }
      }
   }
}

//+------------------------------------------------------------------+
//| Các hàm phụ trợ
//+------------------------------------------------------------------+
void HandleTrailingStop()
{
   if(!UseTrailingStop || Trail_Start_Points <= 0) return;

   long stopLevel = SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL);
   for(int i = PositionsTotal() - 1; i >= 0; i--) {
      ulong ticket = PositionGetTicket(i);
      if(PositionGetSymbol(i) == _Symbol && PositionGetInteger(POSITION_MAGIC) == InpMagicNum) {
         long type = PositionGetInteger(POSITION_TYPE);
         double currentSL = PositionGetDouble(POSITION_SL);
         double currentTP = PositionGetDouble(POSITION_TP);
         double openPrice = PositionGetDouble(POSITION_PRICE_OPEN);
         
         double point = _Point;
         int digits = _Digits;

         if(type == ORDER_TYPE_BUY) {
            double currentBid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
            double profitPoints = (currentBid - openPrice) / point;
            if(profitPoints >= Trail_Start_Points) {
               double newSL = NormalizeDouble(currentBid - (Trail_Distance_Points * point), digits);
               if((currentBid - newSL) / point < stopLevel) newSL = NormalizeDouble(currentBid - (stopLevel * point), digits);
               if(currentSL == 0 || newSL >= currentSL + (Trail_Step_Points * point)) {
                  trade.PositionModify(ticket, newSL, currentTP);
               }
            }
         }
         else if(type == ORDER_TYPE_SELL) {
            double currentAsk = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
            double profitPoints = (openPrice - currentAsk) / point;
            if(profitPoints >= Trail_Start_Points) {
               double newSL = NormalizeDouble(currentAsk + (Trail_Distance_Points * point), digits);
               if((newSL - currentAsk) / point < stopLevel) newSL = NormalizeDouble(currentAsk + (stopLevel * point), digits);
               if(currentSL == 0 || newSL <= currentSL - (Trail_Step_Points * point)) {
                  trade.PositionModify(ticket, newSL, currentTP);
               }
            }
         }
      }
   }
}

void CheckBreakEven()
{
   if(!InpMoveBE) return;
   for(int i = PositionsTotal() - 1; i >= 0; i--) {
      ulong ticket = PositionGetTicket(i);
      if(PositionGetSymbol(i) == _Symbol && PositionGetInteger(POSITION_MAGIC) == InpMagicNum) {
         long type = PositionGetInteger(POSITION_TYPE);
         double openPrice = PositionGetDouble(POSITION_PRICE_OPEN);
         double currentSL = PositionGetDouble(POSITION_SL);
         double currentTP = PositionGetDouble(POSITION_TP);
         
         if(type == ORDER_TYPE_BUY && currentSL < openPrice) {
            double currentBid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
            double initialRisk = openPrice - currentSL; 
            if(currentBid - openPrice >= initialRisk) trade.PositionModify(ticket, NormalizeDouble(openPrice, _Digits), currentTP);
         }
         else if(type == ORDER_TYPE_SELL && (currentSL > openPrice || currentSL == 0)) {
            double currentAsk = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
            double initialRisk = currentSL - openPrice; 
            if(openPrice - currentAsk >= initialRisk) trade.PositionModify(ticket, NormalizeDouble(openPrice, _Digits), currentTP);
         }
      }
   }
}

//+------------------------------------------------------------------+
//| Hàm Vào Lệnh Động (Dynamic Entry)
//+------------------------------------------------------------------+
void ExecuteDynamicMarketEntry(ENUM_ORDER_TYPE type, double slPrice, double tp1, double tp2, double tp3) 
{
   double currentPrice = (type == ORDER_TYPE_BUY) ? SymbolInfoDouble(_Symbol, SYMBOL_ASK) : SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double sl_distance_points = MathAbs(currentPrice - slPrice) / _Point;
   if(sl_distance_points < 50) sl_distance_points = 50; 

   // 1. Tính tổng Lot dựa trên chế độ đã chọn
   double totalLot = 0;
   if(InpLotMode == LOT_AUTO_RISK) {
       totalLot = CalculateLotSize(sl_distance_points);
   } else {
       totalLot = InpFixedLot; // Sử dụng Lot tay
   }

   // 2. Chặn số lượng lệnh (Từ 1 đến 3 lệnh)
   int orders = InpOrderCount;
   if(orders < 1) orders = 1;
   if(orders > 3) orders = 3;

   // 3. Chia đều Lot cho số lệnh thực tế
   double step = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   double min_lot = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   
   double lotPerOrder = MathFloor((totalLot / (double)orders) / step) * step;
   if(lotPerOrder < min_lot) lotPerOrder = min_lot;

   trade.SetExpertMagicNumber(InpMagicNum);
   
   // 4. Bắn lệnh dựa theo cấu hình
   if(type == ORDER_TYPE_BUY) {
      if(orders >= 1) trade.Buy(lotPerOrder, _Symbol, 0, slPrice, tp1, "TrenNova_Buy_TP1");
      if(orders >= 2) trade.Buy(lotPerOrder, _Symbol, 0, slPrice, tp2, "TrenNova_Buy_TP2");
      if(orders >= 3) trade.Buy(lotPerOrder, _Symbol, 0, slPrice, tp3, "TrenNova_Buy_TP3");
   } 
   else {
      if(orders >= 1) trade.Sell(lotPerOrder, _Symbol, 0, slPrice, tp1, "TrenNova_Sell_TP1");
      if(orders >= 2) trade.Sell(lotPerOrder, _Symbol, 0, slPrice, tp2, "TrenNova_Sell_TP2");
      if(orders >= 3) trade.Sell(lotPerOrder, _Symbol, 0, slPrice, tp3, "TrenNova_Sell_TP3");
   }
}

//+------------------------------------------------------------------+
//| Hàm tính Lot theo % Rủi Ro
//+------------------------------------------------------------------+
double CalculateLotSize(double sl_distance_points)
{
   double balance = AccountInfoDouble(ACCOUNT_BALANCE);
   double risk_amount = balance * (InpRiskPercent / 100.0);
   double tick_value = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
   double tick_size = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   double point = SymbolInfoDouble(_Symbol, SYMBOL_POINT);
   
   if(tick_value == 0 || sl_distance_points == 0) return SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   
   double point_value = tick_value * (point / tick_size);
   double raw_lot = risk_amount / (sl_distance_points * point_value);
   
   double min_lot = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double max_lot = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   double step = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   
   raw_lot = MathFloor(raw_lot / step) * step;
   if(raw_lot < min_lot) raw_lot = min_lot;
   if(raw_lot > max_lot) raw_lot = max_lot;
   return raw_lot;
}

double GetSMA(int index) { double b[1]; if(CopyBuffer(handleSMA, 0, index, 1, b) > 0) return b[0]; return 0; }
double GetATR(int index) { double b[1]; if(CopyBuffer(handleATR, 0, index, 1, b) > 0) return b[0]; return 0; }

bool HasBuyPosition() {
   for(int i=PositionsTotal()-1; i>=0; i--) {
      if(PositionGetSymbol(i) == _Symbol && PositionGetInteger(POSITION_MAGIC) == InpMagicNum) {
         if(PositionGetInteger(POSITION_TYPE) == ORDER_TYPE_BUY) return true;
      }
   }
   return false;
}

bool HasSellPosition() {
   for(int i=PositionsTotal()-1; i>=0; i--) {
      if(PositionGetSymbol(i) == _Symbol && PositionGetInteger(POSITION_MAGIC) == InpMagicNum) {
         if(PositionGetInteger(POSITION_TYPE) == ORDER_TYPE_SELL) return true;
      }
   }
   return false;
}
//--- END OF CODE ---