// MT5 Expert Advisor stub — generated from .lang
#property strict

input int   Multiplier = 1;
input double LotSize = 0.1;
// Product.id : I
// Product.name : S
// Product.price : F
// Product.sku : S
// Order.id : I
// Order.uid : I
// Order.total : F
// Order.status : E[Pending,Paid,Shipped]
// Customer.id : I
// Customer.email : S
// Customer.name : S
// Position.id : I
// Position.symbol : S
// Position.volume : F
// Position.price : F
// Position.sl : F
// Position.tp : F
// Signal.symbol : S
// Signal.dir : E[Buy,Sell]
// Signal.strength : F

int OnInit()
{
  return(INIT_SUCCEEDED);
}

void OnTick()
{
  if (!TerminalInfoInteger(TERMINAL_TRADE_ALLOWED)) return;
  // TODO: signals from parsed services / symbols
  // MqlTick tick; SymbolInfoTick(_Symbol, tick);
}

void OnDeinit(const int reason) {}
