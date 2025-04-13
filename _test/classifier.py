import os
import json
import argparse
import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import Dataset, DataLoader
from torchvision import transforms, models
from PIL import Image
from tqdm import tqdm
import matplotlib.pyplot as plt


class ImgSet(Dataset):
	def __init__(self, dir, file, tfm=None):
		self.dir = dir
		with open(file, "r") as f:
			self.imgs = json.load(f)
		self.tfm = tfm
		self.label = 1 if "manga" in os.path.basename(file) else 0

	def __len__(self):
		return len(self.imgs)

	def __getitem__(self, idx):
		name = self.imgs[idx]
		path = os.path.join(self.dir, name)
		img = Image.open(path).convert("RGB")
		if self.tfm:
			img = self.tfm(img)
		return img, self.label


class MangaModel:
	def __init__(self, dir, batch=1, lr=1e-4, epochs=40):
		self.dir = dir
		self.img_dir = os.path.join(dir, "img")
		self.test_dir = os.path.join(dir, "test")
		self.manga_file = os.path.join(self.test_dir, "manga.json")
		self.other_file = os.path.join(self.test_dir, "not_manga.json")
		self.batch = batch
		self.lr = lr
		self.epochs = epochs
		self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
		self.train_tfm = transforms.Compose(
			[
				transforms.Resize((768, 768)),
				transforms.RandomHorizontalFlip(p=0.5),
				transforms.RandomRotation(10),
				transforms.ColorJitter(brightness=0.1, contrast=0.1),
				transforms.ToTensor(),
				transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
			]
		)
		self.val_tfm = transforms.Compose(
			[
				transforms.Resize((768, 768)),
				transforms.ToTensor(),
				transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
			]
		)
		self.accumulation_steps = 4

	def load_data(self):
		manga_ds = ImgSet(self.img_dir, self.manga_file, self.train_tfm)
		other_ds = ImgSet(self.img_dir, self.other_file, self.train_tfm)
		manga_train_size = int(0.8 * len(manga_ds))
		manga_val_size = len(manga_ds) - manga_train_size
		other_train_size = int(0.8 * len(other_ds))
		other_val_size = len(other_ds) - other_train_size
		manga_train, manga_val = torch.utils.data.random_split(
			manga_ds, [manga_train_size, manga_val_size]
		)
		other_train, other_val = torch.utils.data.random_split(
			other_ds, [other_train_size, other_val_size]
		)
		train_ds = torch.utils.data.ConcatDataset([manga_train, other_train])
		val_ds = torch.utils.data.ConcatDataset([manga_val, other_val])
		self.train_dl = DataLoader(
			train_ds,
			batch_size=self.batch,
			shuffle=True,
			num_workers=1,
			pin_memory=False,
		)
		self.val_dl = DataLoader(
			val_ds,
			batch_size=self.batch,
			shuffle=False,
			num_workers=1,
			pin_memory=False,
		)
		weight = len(other_train) / len(manga_train)
		self.pos_weight = torch.tensor([weight]).to(self.device)
		return self.train_dl, self.val_dl

	def build_model(self, arch="efficientnet_v2_l"):
		self.scaler = torch.amp.GradScaler(enabled=True)
		if arch == "efficientnet_v2_l":
			self.model = models.efficientnet_v2_l(weights="IMAGENET1K_V1")
			n = self.model.classifier[1].in_features
			self.model.classifier[1] = nn.Linear(n, 1)
		elif arch == "efficientnet_v2_m":
			self.model = models.efficientnet_v2_m(weights="IMAGENET1K_V1")
			n = self.model.classifier[1].in_features
			self.model.classifier[1] = nn.Linear(n, 1)
		elif arch == "efficientnet_v2_s":
			self.model = models.efficientnet_v2_s(weights="IMAGENET1K_V1")
			n = self.model.classifier[1].in_features
			self.model.classifier[1] = nn.Linear(n, 1)
		self.model = self.model.to(self.device)
		try:
			self.model.set_grad_checkpointing(enable=True)
		except:
			print("Gradient checkpointing not supported for this model, skipping.")
		self.loss_fn = nn.BCEWithLogitsLoss(pos_weight=self.pos_weight)
		self.opt = optim.AdamW(self.model.parameters(), lr=self.lr, weight_decay=0.01)
		self.sched = optim.lr_scheduler.OneCycleLR(
			self.opt,
			max_lr=self.lr,
			steps_per_epoch=len(self.train_dl),
			epochs=self.epochs,
		)
		return self.model

	def train(self):
		best_acc = 0.0
		best_path = os.path.join(self.dir, "best.safetensor")
		hist = {"train_loss": [], "val_loss": [], "val_acc": [], "lr": []}
		os.makedirs(os.path.join(self.dir, "ckpt"), exist_ok=True)
		for epoch in range(self.epochs):
			torch.cuda.empty_cache()
			self.model.train()
			train_loss = 0.0
			bar = tqdm(self.train_dl, desc=f"Epoch {epoch+1}/{self.epochs} [Train]")
			for i, (imgs, lbls) in enumerate(bar):
				imgs = imgs.to(self.device)
				lbls = lbls.to(self.device).float().view(-1, 1)
				if i % self.accumulation_steps == 0:
					self.opt.zero_grad()
				with torch.amp.autocast("cuda"):
					outs = self.model(imgs)
					loss = self.loss_fn(outs, lbls) / self.accumulation_steps
				self.scaler.scale(loss).backward()
				if (i + 1) % self.accumulation_steps == 0 or (i + 1) == len(
					self.train_dl
				):
					self.scaler.step(self.opt)
					self.scaler.update()
					self.opt.zero_grad()
				train_loss += (loss.item() * self.accumulation_steps) * imgs.size(0)
				bar.set_postfix({"loss": loss.item() * self.accumulation_steps})
			torch.cuda.empty_cache()
			train_loss = train_loss / len(self.train_dl.dataset)
			hist["train_loss"].append(train_loss)
			self.model.eval()
			val_loss = 0.0
			correct = 0
			total = 0
			bar = tqdm(self.val_dl, desc=f"Epoch {epoch+1}/{self.epochs} [Val]")
			with torch.no_grad():
				for imgs, lbls in bar:
					imgs = imgs.to(self.device)
					lbls = lbls.to(self.device).float().view(-1, 1)
					with torch.amp.autocast("cuda"):
						outs = self.model(imgs)
						loss = self.loss_fn(outs, lbls)
					val_loss += loss.item() * imgs.size(0)
					preds = (torch.sigmoid(outs) >= 0.5).float()
					correct += (preds == lbls).sum().item()
					total += lbls.size(0)
					bar.set_postfix({"loss": loss.item()})
			torch.cuda.empty_cache()
			val_loss = val_loss / len(self.val_dl.dataset)
			val_acc = correct / total
			hist["val_loss"].append(val_loss)
			hist["val_acc"].append(val_acc)
			hist["lr"].append(self.opt.param_groups[0]["lr"])
			self.sched.step(val_acc)
			if (epoch + 1) % 5 == 0:
				path = os.path.join(self.dir, "ckpt", f"ckpt_{epoch+1}.pth")
				torch.save(
					{
						"epoch": epoch + 1,
						"model": self.model.state_dict(),
						"opt": self.opt.state_dict(),
						"acc": val_acc,
					},
					path,
				)
			if val_acc > best_acc:
				best_acc = val_acc
				torch.save(self.model.state_dict(), best_path)
		self.model.load_state_dict(torch.load(best_path))
		self.plot_hist(hist)
		return hist

	def plot_hist(self, hist):
		_, (ax1, ax2, ax3) = plt.subplots(1, 3, figsize=(15, 5))
		ax1.plot(hist["train_loss"], label="Train")
		ax1.plot(hist["val_loss"], label="Val")
		ax1.set_xlabel("Epoch")
		ax1.set_ylabel("Loss")
		ax1.set_title("Loss")
		ax1.legend()
		ax2.plot(hist["val_acc"], label="Acc")
		ax2.set_xlabel("Epoch")
		ax2.set_ylabel("Acc")
		ax2.set_title("Val Acc")
		ax2.legend()
		ax3.plot(hist["lr"], label="LR")
		ax3.set_xlabel("Epoch")
		ax3.set_ylabel("LR")
		ax3.set_title("LR")
		ax3.set_yscale("log")
		ax3.legend()
		plt.tight_layout()
		plt.savefig(os.path.join(self.dir, "hist.png"))
		plt.close()

	def predict(self, path):
		self.model.eval()
		img = Image.open(path).convert("RGB")
		img = self.val_tfm(img).unsqueeze(0).to(self.device)
		with torch.no_grad():
			with torch.amp.autocast("cuda"):
				out = self.model(img)
				conf = torch.sigmoid(out).item()
		is_manga = conf >= 0.5
		return {"is_manga": bool(is_manga), "conf": conf, "path": path}

	def evaluate(self):
		torch.cuda.empty_cache()
		manga_set = ImgSet(self.img_dir, self.manga_file, self.val_tfm)
		other_set = ImgSet(self.img_dir, self.other_file, self.val_tfm)
		test_set = torch.utils.data.ConcatDataset([manga_set, other_set])
		test_dl = DataLoader(
			test_set,
			batch_size=self.batch,
			shuffle=False,
			num_workers=1,
			pin_memory=False,
		)
		self.model.eval()
		correct = 0
		total = 0
		lbls = []
		preds = []
		confs = []
		with torch.no_grad():
			for imgs, batch_lbls in tqdm(test_dl, desc="Testing"):
				imgs = imgs.to(self.device)
				batch_lbls = batch_lbls.to(self.device)
				with torch.amp.autocast("cuda"):
					outs = self.model(imgs)
					batch_confs = torch.sigmoid(outs).cpu().numpy()
				batch_preds = (batch_confs >= 0.5).astype(int)
				correct += (batch_preds.flatten() == batch_lbls.cpu().numpy()).sum()
				total += batch_lbls.size(0)
				confs.extend(batch_confs.flatten())
				preds.extend(batch_preds.flatten())
				lbls.extend(batch_lbls.cpu().numpy())
				torch.cuda.empty_cache()
		acc = correct / total
		tp = sum((p == 1 and l == 1) for p, l in zip(preds, lbls))
		tn = sum((p == 0 and l == 0) for p, l in zip(preds, lbls))
		fp = sum((p == 1 and l == 0) for p, l in zip(preds, lbls))
		fn = sum((p == 0 and l == 1) for p, l in zip(preds, lbls))
		prec = tp / (tp + fp) if (tp + fp) > 0 else 0
		rec = tp / (tp + fn) if (tp + fn) > 0 else 0
		f1 = 2 * (prec * rec) / (prec + rec) if (prec + rec) > 0 else 0
		results = {
			"acc": float(acc),
			"prec": float(prec),
			"rec": float(rec),
			"f1": float(f1),
			"cm": {"tp": int(tp), "tn": int(tn), "fp": int(fp), "fn": int(fn)},
		}
		with open(os.path.join(self.dir, "results.json"), "w") as f:
			json.dump(results, f, indent="\t", ensure_ascii=False)
		cm = [[tn, fp], [fn, tp]]
		plt.figure(figsize=(8, 6))
		plt.imshow(cm, cmap="Blues")
		plt.colorbar()
		classes = ["Not Manga", "Manga"]
		ticks = [0, 1]
		plt.xticks(ticks, classes)
		plt.yticks(ticks, classes)
		for i in range(2):
			for j in range(2):
				plt.text(
					j,
					i,
					str(cm[i][j]),
					ha="center",
					va="center",
					color="white" if cm[i][j] > len(lbls) / 4 else "black",
				)
		plt.xlabel("Pred")
		plt.ylabel("True")
		plt.title("CM")
		plt.tight_layout()
		plt.savefig(os.path.join(self.dir, "cm.png"))
		plt.close()
		plt.figure(figsize=(10, 6))
		manga_conf = [c for c, l in zip(confs, lbls) if l == 1]
		other_conf = [c for c, l in zip(confs, lbls) if l == 0]
		plt.hist(manga_conf, alpha=0.5, bins=20, label="Manga", color="blue")
		plt.hist(other_conf, alpha=0.5, bins=20, label="Not Manga", color="red")
		plt.xlabel("Conf")
		plt.ylabel("Count")
		plt.title("Conf Dist")
		plt.legend()
		plt.grid(alpha=0.3)
		plt.tight_layout()
		plt.savefig(os.path.join(self.dir, "dist.png"))
		plt.close()
		threshs = np.linspace(0, 1, 100)
		tprs = []
		fprs = []
		for t in threshs:
			pred = [1 if c >= t else 0 for c in confs]
			tp = sum((p == 1 and l == 1) for p, l in zip(pred, lbls))
			fp = sum((p == 1 and l == 0) for p, l in zip(pred, lbls))
			fn = sum((p == 0 and l == 1) for p, l in zip(pred, lbls))
			tn = sum((p == 0 and l == 0) for p, l in zip(pred, lbls))
			tpr = tp / (tp + fn) if (tp + fn) > 0 else 0
			fpr = fp / (fp + tn) if (fp + tn) > 0 else 0
			tprs.append(tpr)
			fprs.append(fpr)
		auc = 0
		for i in range(1, len(fprs)):
			auc += (fprs[i] - fprs[i - 1]) * (tprs[i] + tprs[i - 1]) / 2
		plt.figure(figsize=(8, 8))
		plt.plot(fprs, tprs, "b-", linewidth=2)
		plt.plot([0, 1], [0, 1], "r--", linewidth=2)
		plt.xlabel("FPR")
		plt.ylabel("TPR")
		plt.title(f"ROC (AUC={auc:.4f})")
		plt.grid(alpha=0.3)
		plt.tight_layout()
		plt.savefig(os.path.join(self.dir, "roc.png"))
		plt.close()
		misses = [
			(idx, confs[idx], lbls[idx])
			for idx in range(len(preds))
			if preds[idx] != lbls[idx]
		]
		results["miss_count"] = len(misses)
		results["auc"] = float(auc)
		with open(os.path.join(self.dir, "results.json"), "w") as f:
			json.dump(results, f, indent="\t", ensure_ascii=False)
		return results

	def export(self, path=None):
		if path is None:
			path = os.path.join(self.dir, "model.onnx")
		torch.cuda.empty_cache()
		dummy = torch.randn(1, 3, 768, 768, device=self.device)
		torch.onnx.export(
			self.model,
			dummy,
			path,
			export_params=True,
			opset_version=12,
			do_constant_folding=True,
			input_names=["input"],
			output_names=["output"],
			dynamic_axes={"input": {0: "batch"}, "output": {0: "batch"}},
		)
		return path


def main():
	parser = argparse.ArgumentParser(description="Manga Classifier")
	parser.add_argument("dir", type=str, help="Data dir with img and test folders")
	parser.add_argument("--batch", type=int, default=1, help="Batch size")
	parser.add_argument("--lr", type=float, default=1e-4, help="Learning rate")
	parser.add_argument("--epochs", type=int, default=40, help="Epochs")
	parser.add_argument(
		"--arch",
		type=str,
		default="efficientnet_v2_l",
		choices=["efficientnet_v2_l", "efficientnet_v2_m", "efficientnet_v2_s"],
		help="Model arch",
	)
	parser.add_argument("--export", action="store_true", help="Export ONNX")
	args = parser.parse_args()
	if torch.cuda.is_available():
		torch.backends.cudnn.benchmark = True
		torch.backends.cuda.matmul.allow_tf32 = True
		torch.backends.cudnn.allow_tf32 = True
		os.environ["PYTORCH_CUDA_ALLOC_CONF"] = (
			"expandable_segments:True,garbage_collection_threshold:0.6,max_split_size_mb:128"
		)
	torch.cuda.empty_cache()
	model = MangaModel(args.dir, batch=args.batch, lr=args.lr, epochs=args.epochs)
	model.load_data()
	model.build_model(arch=args.arch)
	model.train()
	model.evaluate()
	if args.export:
		model.export()


if __name__ == "__main__":
	main()
