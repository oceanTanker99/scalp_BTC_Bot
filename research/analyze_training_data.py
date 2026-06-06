import pandas as pd

def analyze():
    df = pd.read_csv('logs/training_dataset.csv')
    
    print("="*50)
    print("🧠 HASIL ANALISIS POLA KEGAGALAN (ML PREP)")
    print("="*50)
    
    # 1. Evaluasi Filter PSO
    print("\n1️⃣ EVALUASI FILTER MATEMATIKA (PSO)")
    pso_data = df[df['rejection_reason'] != 'PASSED']
    pso_saved = pso_data[pso_data['outcome'] == 'LOSS']
    pso_missed = pso_data[pso_data['outcome'] == 'WIN']
    
    print(f"Total Sinyal Ditolak PSO: {len(pso_data)}")
    if len(pso_data) > 0:
        print(f"- PSO Benar (Menyelamatkan dari LOSS) : {len(pso_saved)} ({(len(pso_saved)/len(pso_data))*100:.1f}%)")
        print(f"- PSO Salah (Melewatkan WIN)          : {len(pso_missed)} ({(len(pso_missed)/len(pso_data))*100:.1f}%)")
    
    # 2. Evaluasi Sinyal yang "Lolos" (PASSED) berdasarkan Strategy Type
    print("\n2️⃣ WIN RATE SINYAL PASSED (BERDASARKAN REZIM STRATEGI)")
    passed_data = df[df['rejection_reason'] == 'PASSED']
    
    for strat in ['MEAN_REVERSION', 'TREND_FOLLOWING']:
        strat_df = passed_data[passed_data['strategy_type'] == strat]
        wins = len(strat_df[strat_df['outcome'] == 'WIN'])
        losses = len(strat_df[strat_df['outcome'] == 'LOSS'])
        be = len(strat_df[strat_df['outcome'] == 'UNKNOWN']) # Not hit
        total_resolved = wins + losses
        win_rate = (wins / total_resolved) * 100 if total_resolved > 0 else 0
        print(f"{strat}: Win {wins} | Loss {losses} | WR: {win_rate:.1f}%")
        
    # 3. Analisis Kekurangan "Trend-Following" yang sering LOSS
    print("\n3️⃣ ANALISIS KESALAHAN PADA TREND-FOLLOWING")
    tf_losses = passed_data[(passed_data['strategy_type'] == 'TREND_FOLLOWING') & (passed_data['outcome'] == 'LOSS')]
    tf_wins = passed_data[(passed_data['strategy_type'] == 'TREND_FOLLOWING') & (passed_data['outcome'] == 'WIN')]
    
    if len(tf_losses) > 0 and len(tf_wins) > 0:
        print("Rata-rata Indikator saat Menang vs Kalah:")
        print(f"- ADX saat Menang : {tf_wins['adx'].mean():.1f} | Kalah: {tf_losses['adx'].mean():.1f}")
        print(f"- DMI Diff Menang : {tf_wins['dmi_diff'].mean():.1f} | Kalah: {tf_losses['dmi_diff'].mean():.1f}")
        print(f"- Jarak EMA800 (%) saat Menang: {tf_wins['dist_ema800_pct'].mean():.1f}% | Kalah: {tf_losses['dist_ema800_pct'].mean():.1f}%")
        print(f"- BB Width (%) saat Menang    : {tf_wins['bb_width'].mean():.1f}% | Kalah: {tf_losses['bb_width'].mean():.1f}%")

    print("\n4️⃣ BREAKDOWN BERDASARKAN KONDISI PASAR")
    for regime in df['regime'].unique():
        r_df = passed_data[passed_data['regime'] == regime]
        rw = len(r_df[r_df['outcome'] == 'WIN'])
        rl = len(r_df[r_df['outcome'] == 'LOSS'])
        total_r = rw + rl
        wr = (rw / total_r) * 100 if total_r > 0 else 0
        print(f"[{regime}] Sinyal Lolos: {len(r_df)} | Win Rate: {wr:.1f}%")

if __name__ == "__main__":
    analyze()
