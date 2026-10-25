# Git overview

Git tracks source-code changes. A repository contains commits, branches, and
the history needed to collaborate safely.

# Git setup and help

Check the installed Git version and command help:

```bash
git --version
git help
git <command> --help
```

Configure the author identity used in commits:

```bash
git config --global user.name "Your Name"
git config --global user.email "you@example.com"
git config --list
```

# Create a Git repository

Create a repository in the current directory:

```bash
git init
```

# Clone an existing repository

Copy an existing remote repository:

```bash
git clone <repository-url>
cd <repository-directory>
```

# Manage remote repositories

Show the remote URLs:

```bash
git remote -v
```

Add or change a remote:

```bash
git remote add origin <repository-url>
git remote set-url origin <repository-url>
```

# Status and history

See changed, untracked, and staged files:

```bash
git status
```

View commit history:

```bash
git log --oneline --graph --decorate --all
git log -p
```

Show changes that are not staged or are already staged:

```bash
git diff
git diff --staged
```

Show one commit:

```bash
git show <commit>
```

# Staging and commits

Stage one file or all current changes:

```bash
git add app.py
git add .
```

Remove a file from the next commit while keeping it on disk:

```bash
git restore --staged <file>
```

Create a commit:

```bash
git commit -m "Add health endpoint"
```

Amend the latest commit only when it has not been shared:

```bash
git commit --amend
```

# Branches

List branches, create one, and switch to it:

```bash
git branch
git switch -c feature/chatbot-search
git switch main
```

Delete a merged local branch:

```bash
git branch -d feature/chatbot-search
```

Merge another branch into the current branch:

```bash
git merge feature/chatbot-search
```

# Remote collaboration

Download remote updates without changing local files:

```bash
git fetch origin
```

Update the current branch:

```bash
git pull --rebase origin main
```

Publish a new branch and remember its upstream:

```bash
git push --set-upstream origin feature/chatbot-search
```

Push the current branch:

```bash
git push
```

# Undoing changes safely

Discard changes in one unstaged file. This permanently removes those local
changes:

```bash
git restore <file>
```

Restore a file from a specific commit:

```bash
git restore --source=<commit> -- <file>
```

Create a new commit that reverses an earlier commit:

```bash
git revert <commit>
```

Do not use `git reset --hard` unless you are certain that uncommitted work can
be deleted.

# Tags and releases

Create and list version tags:

```bash
git tag v1.0.0
git tag
```

Push a tag:

```bash
git push origin v1.0.0
```

# Ignoring files

Place generated files, virtual environments, credentials, and local settings
in `.gitignore`. Never commit passwords, API keys, private certificates, or
`.env` files containing secrets.
