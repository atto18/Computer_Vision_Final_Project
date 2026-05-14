"""
STEP 3 — TRAIN GESTURE CLASSIFIER
====================================
Run this after extract_features.py.
Trains a 3-layer MLP on your gesture dataset CSV.
Saves the trained model, scaler, and label encoder.
Generates confusion matrix and training curves.

HOW TO RUN:
    python train_gesture_model.py

OUTPUT:
    dataset/models/gesture_model.pth       <- trained model
    dataset/models/scaler.pkl              <- feature normalizer
    dataset/models/label_encoder.pkl       <- class name mapping
    dataset/models/training_curves.png     <- loss & accuracy plots
    dataset/models/confusion_matrix.png    <- evaluation visualization
"""

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader, TensorDataset
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler, LabelEncoder
from sklearn.metrics import (confusion_matrix, classification_report,
                              f1_score, precision_score, recall_score)
import matplotlib.pyplot as plt
import matplotlib
matplotlib.use('Agg')
import seaborn as sns
import pickle
import os
import sys

# ── CONFIG ────────────────────────────────────────────────────────────────
DATASET_ROOT = r"C:\Users\ahmad\Desktop\ESIB_USJ\4_ème_année\Semestre_2\Computer Vision\Final_Project\dataset"
CSV_PATH     = r"C:\Users\ahmad\Desktop\ESIB_USJ\4_ème_année\Semestre_2\Computer Vision\Final_Project\dataset\gesture_dataset.csv"
MODELS_DIR   = r"C:\Users\ahmad\Desktop\ESIB_USJ\4_ème_année\Semestre_2\Computer Vision\Final_Project\dataset\gesture_models"

# Training hyperparameters
EPOCHS        = 60
BATCH_SIZE    = 32
LEARNING_RATE = 0.001
DROPOUT_RATE  = 0.3
HIDDEN1       = 128
HIDDEN2       = 64
TRAIN_SPLIT   = 0.70
VAL_SPLIT     = 0.15
TEST_SPLIT    = 0.15
RANDOM_SEED   = 42

# ── MODEL ─────────────────────────────────────────────────────────────────
class GestureClassifier(nn.Module):
    """
    3-layer MLP for gesture classification.
    Input: feature vector (45 values)
    Output: class probabilities (7 classes)
    """
    def __init__(self, input_dim, num_classes, hidden1=128, hidden2=64, dropout=0.3):
        super(GestureClassifier, self).__init__()

        self.network = nn.Sequential(
            # Layer 1
            nn.Linear(input_dim, hidden1),
            nn.BatchNorm1d(hidden1),
            nn.ReLU(),
            nn.Dropout(dropout),

            # Layer 2
            nn.Linear(hidden1, hidden2),
            nn.BatchNorm1d(hidden2),
            nn.ReLU(),
            nn.Dropout(dropout * 0.7),

            # Output layer
            nn.Linear(hidden2, num_classes)
        )

    def forward(self, x):
        return self.network(x)

# ── TRAINING LOOP ─────────────────────────────────────────────────────────
def train_epoch(model, loader, criterion, optimizer, device):
    model.train()
    total_loss, correct, total = 0, 0, 0
    for X_batch, y_batch in loader:
        X_batch, y_batch = X_batch.to(device), y_batch.to(device)
        optimizer.zero_grad()
        outputs = model(X_batch)
        loss    = criterion(outputs, y_batch)
        loss.backward()
        optimizer.step()
        total_loss += loss.item() * len(y_batch)
        preds      = outputs.argmax(dim=1)
        correct    += (preds == y_batch).sum().item()
        total      += len(y_batch)
    return total_loss / total, correct / total

def eval_epoch(model, loader, criterion, device):
    model.eval()
    total_loss, correct, total = 0, 0, 0
    with torch.no_grad():
        for X_batch, y_batch in loader:
            X_batch, y_batch = X_batch.to(device), y_batch.to(device)
            outputs    = model(X_batch)
            loss       = criterion(outputs, y_batch)
            total_loss += loss.item() * len(y_batch)
            preds      = outputs.argmax(dim=1)
            correct    += (preds == y_batch).sum().item()
            total      += len(y_batch)
    return total_loss / total, correct / total

# ── PLOTS ─────────────────────────────────────────────────────────────────
def plot_training_curves(train_losses, val_losses, train_accs, val_accs, save_path):
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))
    fig.suptitle('GestureWar — Training Curves', fontsize=14, fontweight='bold')

    epochs = range(1, len(train_losses) + 1)

    ax1.plot(epochs, train_losses, 'b-',  label='Train Loss',      linewidth=2)
    ax1.plot(epochs, val_losses,   'r--', label='Validation Loss', linewidth=2)
    ax1.set_title('Loss')
    ax1.set_xlabel('Epoch')
    ax1.set_ylabel('Cross-Entropy Loss')
    ax1.legend()
    ax1.grid(True, alpha=0.3)

    ax2.plot(epochs, [a*100 for a in train_accs], 'b-',  label='Train Accuracy',      linewidth=2)
    ax2.plot(epochs, [a*100 for a in val_accs],   'r--', label='Validation Accuracy', linewidth=2)
    ax2.set_title('Accuracy')
    ax2.set_xlabel('Epoch')
    ax2.set_ylabel('Accuracy (%)')
    ax2.set_ylim([0, 100])
    ax2.legend()
    ax2.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig(save_path, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"  Training curves saved: {save_path}")

def plot_confusion_matrix(y_true, y_pred, class_names, save_path):
    cm = confusion_matrix(y_true, y_pred)
    cm_norm = cm.astype('float') / cm.sum(axis=1)[:, np.newaxis]

    fig, ax = plt.subplots(figsize=(10, 8))
    sns.heatmap(cm_norm, annot=True, fmt='.2f', cmap='Blues',
                xticklabels=class_names, yticklabels=class_names,
                ax=ax, vmin=0, vmax=1)
    ax.set_title('GestureWar — Confusion Matrix (Normalized)', fontsize=13, fontweight='bold')
    ax.set_ylabel('True Label', fontsize=11)
    ax.set_xlabel('Predicted Label', fontsize=11)
    plt.xticks(rotation=45, ha='right', fontsize=9)
    plt.yticks(rotation=0, fontsize=9)
    plt.tight_layout()
    plt.savefig(save_path, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"  Confusion matrix saved: {save_path}")

# ── MAIN ──────────────────────────────────────────────────────────────────
def main():
    print("=" * 60)
    print("  GestureWar — Gesture Classifier Training")
    print("=" * 60)

    os.makedirs(MODELS_DIR, exist_ok=True)

    # ── Load data ─────────────────────────────────────────────────────────
    print(f"\nLoading dataset: {CSV_PATH}")
    if not os.path.exists(CSV_PATH):
        print("ERROR: dataset.csv not found. Run extract_features.py first.")
        sys.exit(1)

    df = pd.read_csv(CSV_PATH)
    print(f"  Total samples : {len(df)}")
    print(f"  Feature dim   : {len(df.columns) - 1}")
    print(f"  Classes found : {df['label'].nunique()}")
    print()

    # Class distribution
    print("Class distribution:")
    for cls, count in df['label'].value_counts().items():
        bar = "█" * (count // 20)
        print(f"  {cls:<35} {count:>5}  {bar}")
    print()

    # ── Encode labels ─────────────────────────────────────────────────────
    le = LabelEncoder()
    y  = le.fit_transform(df['label'].values)
    X  = df.drop('label', axis=1).values.astype(np.float32)

    num_classes = len(le.classes_)
    input_dim   = X.shape[1]
    class_names = le.classes_

    print(f"Classes: {list(class_names)}")
    print(f"Input dim: {input_dim}, Num classes: {num_classes}")

    # ── Train/val/test split ──────────────────────────────────────────────
    X_train, X_temp, y_train, y_temp = train_test_split(
        X, y, test_size=(VAL_SPLIT + TEST_SPLIT),
        random_state=RANDOM_SEED, stratify=y)

    X_val, X_test, y_val, y_test = train_test_split(
        X_temp, y_temp,
        test_size=TEST_SPLIT / (VAL_SPLIT + TEST_SPLIT),
        random_state=RANDOM_SEED, stratify=y_temp)

    print(f"\nSplit — Train: {len(X_train)} | Val: {len(X_val)} | Test: {len(X_test)}")

    # ── Normalize features ────────────────────────────────────────────────
    scaler  = StandardScaler()
    X_train = scaler.fit_transform(X_train)
    X_val   = scaler.transform(X_val)
    X_test  = scaler.transform(X_test)

    # ── Create data loaders ───────────────────────────────────────────────
    def to_loader(X, y, shuffle=True):
        dataset = TensorDataset(
            torch.FloatTensor(X),
            torch.LongTensor(y))
        return DataLoader(dataset, batch_size=BATCH_SIZE, shuffle=shuffle)

    train_loader = to_loader(X_train, y_train, shuffle=True)
    val_loader   = to_loader(X_val,   y_val,   shuffle=False)
    test_loader  = to_loader(X_test,  y_test,  shuffle=False)

    # ── Build model ───────────────────────────────────────────────────────
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print(f"\nDevice: {device}")

    model     = GestureClassifier(input_dim, num_classes, HIDDEN1, HIDDEN2, DROPOUT_RATE).to(device)
    criterion = nn.CrossEntropyLoss()
    optimizer = optim.Adam(model.parameters(), lr=LEARNING_RATE, weight_decay=1e-4)
    scheduler = optim.lr_scheduler.ReduceLROnPlateau(optimizer, patience=8, factor=0.5)

    print(f"\nModel parameters: {sum(p.numel() for p in model.parameters()):,}")
    print()

    # ── Training ──────────────────────────────────────────────────────────
    print(f"Training for {EPOCHS} epochs...")
    print(f"{'Epoch':>6} {'Train Loss':>12} {'Train Acc':>10} {'Val Loss':>10} {'Val Acc':>10}")
    print("-" * 55)

    train_losses, val_losses   = [], []
    train_accs,   val_accs     = [], []
    best_val_acc = 0
    best_model_path = os.path.join(MODELS_DIR, "gesture_model.pth")

    for epoch in range(1, EPOCHS + 1):
        tr_loss, tr_acc = train_epoch(model, train_loader, criterion, optimizer, device)
        vl_loss, vl_acc = eval_epoch(model, val_loader,   criterion, device)

        scheduler.step(vl_loss)

        train_losses.append(tr_loss)
        val_losses.append(vl_loss)
        train_accs.append(tr_acc)
        val_accs.append(vl_acc)

        # Save best model
        if vl_acc > best_val_acc:
            best_val_acc = vl_acc
            torch.save({
                'epoch':       epoch,
                'model_state': model.state_dict(),
                'val_acc':     vl_acc,
                'input_dim':   input_dim,
                'num_classes': num_classes,
                'hidden1':     HIDDEN1,
                'hidden2':     HIDDEN2,
                'dropout':     DROPOUT_RATE,
            }, best_model_path)
            marker = " ← best"
        else:
            marker = ""

        if epoch % 5 == 0 or epoch == 1:
            print(f"{epoch:>6} {tr_loss:>12.4f} {tr_acc*100:>9.1f}% "
                  f"{vl_loss:>10.4f} {vl_acc*100:>9.1f}%{marker}")

    print()
    print(f"Best validation accuracy: {best_val_acc*100:.1f}%")

    # ── Test evaluation ───────────────────────────────────────────────────
    print("\nEvaluating on test set...")

    # Load best model
    checkpoint = torch.load(best_model_path, map_location=device)
    model.load_state_dict(checkpoint['model_state'])
    model.eval()

    all_preds, all_true = [], []
    with torch.no_grad():
        for X_batch, y_batch in test_loader:
            X_batch = X_batch.to(device)
            outputs = model(X_batch)
            preds   = outputs.argmax(dim=1).cpu().numpy()
            all_preds.extend(preds)
            all_true.extend(y_batch.numpy())

    test_acc = np.mean(np.array(all_preds) == np.array(all_true))

    print(f"\n{'='*60}")
    print(f"  TEST RESULTS")
    print(f"{'='*60}")
    print(f"  Test Accuracy : {test_acc*100:.2f}%")
    print(f"  Macro F1      : {f1_score(all_true, all_preds, average='macro')*100:.2f}%")
    print()
    print(classification_report(
        all_true, all_preds,
        target_names=class_names,
        digits=3))

    # ── Save plots ────────────────────────────────────────────────────────
    print("Saving evaluation plots...")
    plot_training_curves(
        train_losses, val_losses, train_accs, val_accs,
        os.path.join(MODELS_DIR, "training_curves.png"))
    plot_confusion_matrix(
        all_true, all_preds, class_names,
        os.path.join(MODELS_DIR, "confusion_matrix.png"))

    # ── Save scaler and label encoder ────────────────────────────────────
    scaler_path = os.path.join(MODELS_DIR, "scaler.pkl")
    le_path     = os.path.join(MODELS_DIR, "label_encoder.pkl")

    with open(scaler_path, 'wb') as f:
        pickle.dump(scaler, f)
    with open(le_path, 'wb') as f:
        pickle.dump(le, f)

    print(f"\n  Model saved   : {best_model_path}")
    print(f"  Scaler saved  : {scaler_path}")
    print(f"  Encoder saved : {le_path}")

    print()
    print("Next step: run  python label_spawn_zones.py  (for battlefield)")
    print("       or: run  python game.py               (to test the game)")

if __name__ == "__main__":
    torch.manual_seed(RANDOM_SEED)
    np.random.seed(RANDOM_SEED)
    main()
