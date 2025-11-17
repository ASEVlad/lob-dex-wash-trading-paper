#include <Rcpp.h>
using namespace Rcpp;

// [[Rcpp::plugins(cpp11)]]

// [[Rcpp::export]]
DataFrame detect_label_wash_trades_all_windows(DataFrame df, double margin = 0.1) {
  int n = df.nrows();
  
  StringVector buyers = df["buyer"];
  StringVector sellers = df["seller"];
  NumericVector amounts = df["amount"];
  LogicalVector wash = df["wash_label"];
  
  // ---- Step 1: collect all unique trader IDs ----
  std::set<std::string> traderSet;
  for (int i = 0; i < n; i++) {
    traderSet.insert(Rcpp::as<std::string>(buyers[i]));
    traderSet.insert(Rcpp::as<std::string>(sellers[i]));
  }
  
  std::vector<std::string> traders(traderSet.begin(), traderSet.end());
  int T = traders.size();
  
  // map trader -> index
  std::unordered_map<std::string,int> traderToIdx;
  for (int t = 0; t < T; t++)
    traderToIdx[traders[t]] = t;
  
  // ---- Step 2: prefix balances matrix ----
  // prefixBalance[k][t] = balance of trader t after trades[0..k]
  NumericMatrix prefixBalance(n, T);
  
  // initialize first row from trade 0
  {
    int b = traderToIdx[Rcpp::as<std::string>(buyers[0])];
    int s = traderToIdx[Rcpp::as<std::string>(sellers[0])];
    prefixBalance(0, b) += amounts[0];
    prefixBalance(0, s) -= amounts[0];
  }
  
  // fill remaining rows
  for (int k = 1; k < n; k++) {
    // copy previous balances
    for (int t = 0; t < T; t++)
      prefixBalance(k, t) = prefixBalance(k - 1, t);
    
    // apply trade k
    int b = traderToIdx[Rcpp::as<std::string>(buyers[k])];
    int s = traderToIdx[Rcpp::as<std::string>(sellers[k])];
    
    prefixBalance(k, b) += amounts[k];
    prefixBalance(k, s) -= amounts[k];
  }
  
  // ---- Step 3: prefix sum of trade amounts ----
  NumericVector prefixSum(n);
  prefixSum[0] = amounts[0];
  for (int i = 1; i < n; i++)
    prefixSum[i] = prefixSum[i - 1] + amounts[i];
  
  // ---- Step 4: check all windows [i..j] ----
  for (int i = 0; i < n; i++) {
    for (int j = i; j < n; j++) {
      
      int count = j - i + 1;
      
      // mean trade volume in [i..j]
      double sumVol = (i == 0 ? prefixSum[j] : prefixSum[j] - prefixSum[i - 1]);
      double meanVol = sumVol / count;
      
      // compute balances via prefix difference
      bool ok = true;
      for (int t = 0; t < T; t++) {
        double bal =
          (i == 0 ? prefixBalance(j, t)
             : prefixBalance(j, t) - prefixBalance(i - 1, t));
        double rel = std::abs(bal / meanVol);
        if (rel > margin) {
          ok = false;
          break;
        }
      }
      
      if (ok) {
        // mark all trades i..j as wash
        for (int k = i; k <= j; k++)
          wash[k] = true;
        
        df["wash_label"] = wash;
        return df;
      }
    }
  }
  
  return df; // no window matched
}
