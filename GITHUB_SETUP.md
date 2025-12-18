# 🚀 GitHub Repository Setup Guide

Complete step-by-step guide to push your RAG Profile Agent project to GitHub.

---

## 📋 Prerequisites

Before starting, ensure you have:

- ✅ Git installed on your system
- ✅ GitHub account created
- ✅ GitHub authentication configured (SSH key or Personal Access Token)

### Check Git Installation

```bash
git --version
# Should show: git version 2.x.x or higher
```

If Git is not installed:

**Ubuntu/Debian**:
```bash
sudo apt-get update
sudo apt-get install git
```

**macOS**:
```bash
brew install git
```

**Windows**:
Download from [git-scm.com](https://git-scm.com/download/win)

---

## 🔐 Step 1: Configure Git (If Not Already Done)

Set your Git username and email (used for commits):

```bash
git config --global user.name "Your Name"
git config --global user.email "your.email@example.com"
```

Verify configuration:
```bash
git config --global --list
```

---

## 🆕 Step 2: Create GitHub Repository

### Option A: Using GitHub Website (Recommended)

1. **Go to GitHub**: https://github.com/new

2. **Fill in repository details**:
   - **Repository name**: `rag-profile-agent` (or your preferred name)
   - **Description**: `RAG-based Profile Agent API with LangGraph and FastAPI`
   - **Visibility**: 
     - ✅ **Public** - Anyone can see it
     - ✅ **Private** - Only you (and collaborators) can see it
   - **⚠️ DO NOT** check:
     - ❌ "Add a README file" (you already have one)
     - ❌ "Add .gitignore" (you already have one)
     - ❌ "Choose a license" (you can add this later)
   
3. **Click "Create repository"**

4. **Copy the repository URL**:
   - **HTTPS**: `https://github.com/YOUR_USERNAME/rag-profile-agent.git`
   - **SSH**: `git@github.com:YOUR_USERNAME/rag-profile-agent.git`

### Option B: Using GitHub CLI (If Installed)

```bash
gh repo create rag-profile-agent --public --description "RAG-based Profile Agent API with LangGraph and FastAPI"
```

---

## 🔧 Step 3: Initialize Git Repository (Local)

Navigate to your project directory:

```bash
cd /home/azim/rag-profile-agent
```

Initialize Git repository:

```bash
git init
```

This creates a `.git` directory in your project.

---

## 📝 Step 4: Add Files to Git

### Check what will be added:

```bash
git status
```

You should see all your project files listed as "untracked files".

### Add all files:

```bash
git add .
```

This stages all files for commit (respects `.gitignore` rules).

**Important**: Your `.gitignore` file should prevent sensitive files from being added:
- `.env` files (contain API keys)
- `venv/` directory (virtual environment)
- `__pycache__/` directories
- `.pytest_cache/` directory
- etc.

### Verify what's staged:

```bash
git status
```

You should see files listed under "Changes to be committed".

---

## 💾 Step 5: Create Initial Commit

Create your first commit:

```bash
git commit -m "Initial commit: RAG Profile Agent with FastAPI, LangGraph, and OpenAI integration"
```

**Good commit message practices**:
- Start with a capital letter
- Use imperative mood ("Add feature" not "Added feature")
- Keep it concise but descriptive
- Can be multiple lines for detailed explanations

**Example detailed commit message**:
```bash
git commit -m "Initial commit: RAG Profile Agent

- FastAPI-based API with WebSocket support
- LangGraph agent workflow orchestration
- Modular RAG architecture with hybrid retrieval
- PostgreSQL with pgvector for vector search
- Redis for session memory and caching
- Celery for background task processing
- Comprehensive test suite (38 tests)
- Docker Compose setup for easy deployment
"
```

---

## 🔗 Step 6: Connect to GitHub Repository

### Add Remote Repository

Replace `YOUR_USERNAME` with your GitHub username:

**Using HTTPS** (requires authentication):
```bash
git remote add origin https://github.com/YOUR_USERNAME/rag-profile-agent.git
```

**Using SSH** (if you have SSH keys set up):
```bash
git remote add origin git@github.com:YOUR_USERNAME/rag-profile-agent.git
```

### Verify Remote:

```bash
git remote -v
```

Should show:
```
origin  https://github.com/YOUR_USERNAME/rag-profile-agent.git (fetch)
origin  https://github.com/YOUR_USERNAME/rag-profile-agent.git (push)
```

---

## 📤 Step 7: Push to GitHub

### Push to Main Branch:

```bash
git branch -M main
git push -u origin main
```

**What this does**:
- `git branch -M main` - Renames current branch to `main` (GitHub's default)
- `git push -u origin main` - Pushes to GitHub and sets upstream tracking

### Authentication

If using HTTPS, you'll be prompted for credentials:

**Option 1: Personal Access Token (Recommended)**
1. Create token: https://github.com/settings/tokens
2. Select scopes: `repo` (full control of private repositories)
3. Copy token
4. Use token as password when prompted

**Option 2: GitHub CLI Authentication**
```bash
gh auth login
```

**Option 3: SSH Keys (Recommended for frequent use)**
1. Generate SSH key: `ssh-keygen -t ed25519 -C "your.email@example.com"`
2. Add to GitHub: https://github.com/settings/keys
3. Use SSH URL for remote

---

## ✅ Step 8: Verify on GitHub

1. **Open your repository**: https://github.com/YOUR_USERNAME/rag-profile-agent

2. **Verify files are there**:
   - ✅ `README.md` should be visible
   - ✅ All source code files
   - ✅ Configuration files
   - ❌ `.env` should NOT be there (ignored)
   - ❌ `venv/` should NOT be there (ignored)

3. **Check README rendering**: The README.md should render nicely on GitHub

---

## 🔄 Step 9: Future Updates (Making Changes)

When you make changes to your code:

```bash
# 1. Check what changed
git status

# 2. Add changed files
git add .

# Or add specific files
git add app/api/v1/chat.py
git add README.md

# 3. Commit changes
git commit -m "Update chat endpoint with rate limiting"

# 4. Push to GitHub
git push
```

---

## 📚 Additional Git Commands Reference

### View Changes:
```bash
# Show modified files
git status

# Show detailed changes
git diff

# Show changes in staged files
git diff --staged
```

### View History:
```bash
# Show commit history
git log

# Show compact history
git log --oneline --graph --all
```

### Branch Management:
```bash
# Create new branch
git checkout -b feature/new-feature

# Switch branches
git checkout main

# List branches
git branch

# Merge branch
git checkout main
git merge feature/new-feature
```

### Undo Changes:
```bash
# Unstage files (keep changes)
git reset HEAD <file>

# Discard changes in working directory
git checkout -- <file>

# Undo last commit (keep changes)
git reset --soft HEAD~1
```

---

## 🔒 Security Checklist

Before pushing, ensure:

- ✅ **`.env` file is in `.gitignore`** (contains API keys)
- ✅ **No API keys in code** - Use environment variables
- ✅ **No passwords in code** - Use environment variables
- ✅ **No sensitive data** - Database credentials, etc.
- ✅ **`venv/` is ignored** - Virtual environment shouldn't be committed
- ✅ **`.pytest_cache/` is ignored** - Test cache files

### Check for sensitive data:

```bash
# Search for potential secrets (run before committing)
grep -r "sk-" app/ scripts/  # OpenAI API keys
grep -r "password" app/ --include="*.py"  # Hardcoded passwords
grep -r "secret" app/ --include="*.py"  # Secret keys
```

---

## 📋 Recommended: Add License

Add a LICENSE file to your repository:

1. **Create LICENSE file**:
   ```bash
   # Choose a license (MIT is common for open source)
   touch LICENSE
   ```

2. **Add MIT License content** (example):
   ```
   MIT License

   Copyright (c) 2024 Your Name

   Permission is hereby granted, free of charge, to any person obtaining a copy
   of this software and associated documentation files (the "Software"), to deal
   in the Software without restriction, including without limitation the rights
   to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
   copies of the Software, and to permit persons to whom the Software is
   furnished to do so, subject to the following conditions:

   The above copyright notice and this permission notice shall be included in all
   copies or substantial portions of the Software.

   THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
   IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
   FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
   AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
   LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
   OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
   SOFTWARE.
   ```

3. **Commit and push**:
   ```bash
   git add LICENSE
   git commit -m "Add MIT License"
   git push
   ```

---

## 🔧 Troubleshooting

### Issue: "fatal: remote origin already exists"

**Solution**: Remove and re-add:
```bash
git remote remove origin
git remote add origin https://github.com/YOUR_USERNAME/rag-profile-agent.git
```

### Issue: "Permission denied (publickey)"

**Solution**: Set up SSH keys or use HTTPS with Personal Access Token:
```bash
# Check SSH keys
ssh -T git@github.com

# If fails, generate new key
ssh-keygen -t ed25519 -C "your.email@example.com"
# Then add to GitHub: https://github.com/settings/keys
```

### Issue: "Large files" warning

**Solution**: Ensure large files are in `.gitignore`:
```bash
# Add to .gitignore
*.pdf
*.zip
*.tar.gz
models/
data/
```

### Issue: "Authentication failed"

**Solution**: Use Personal Access Token instead of password:
1. Go to: https://github.com/settings/tokens
2. Generate new token with `repo` scope
3. Use token as password

---

## 🎯 Quick Start Commands (Copy-Paste)

If you've already completed steps 1-2, here's the quick version:

```bash
# Navigate to project
cd /home/azim/rag-profile-agent

# Initialize git
git init

# Add all files
git add .

# Commit
git commit -m "Initial commit: RAG Profile Agent with FastAPI, LangGraph, and OpenAI integration"

# Add remote (replace YOUR_USERNAME)
git remote add origin https://github.com/YOUR_USERNAME/rag-profile-agent.git

# Push to GitHub
git branch -M main
git push -u origin main
```

---

## 📖 Next Steps

After pushing to GitHub:

1. ✅ **Add repository description** on GitHub
2. ✅ **Add topics/tags** (e.g., `python`, `fastapi`, `rag`, `langchain`)
3. ✅ **Enable GitHub Actions** (if using CI/CD)
4. ✅ **Add collaborators** (if working in team)
5. ✅ **Create releases** for version tags
6. ✅ **Set up branch protection** (for main branch)

---

## 🆘 Need Help?

- **Git Documentation**: https://git-scm.com/doc
- **GitHub Help**: https://docs.github.com
- **Git Cheat Sheet**: https://education.github.com/git-cheat-sheet-education.pdf

---

**🎉 Congratulations! Your project is now on GitHub!**

