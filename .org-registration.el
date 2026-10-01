;;; .org-registration.el template
;; Copy this file to an external repo as `.org-registration.el`
;; and adjust paths/templates for that repo.

(defconst project-org-repo-root
  (file-name-directory (or load-file-name buffer-file-name default-directory))
  "Repo root directory for this .org-registration.el file.")

(setq project-org-repo-registration
      `(:agenda-files
        (,(expand-file-name "notes/*.org" project-org-repo-root)
         ,(expand-file-name "projects/**/*.org" project-org-repo-root)
         ,(expand-file-name "TODO.org" project-org-repo-root))
        :capture-templates
        (("r" "External")
         ("rx" "External RxP Task Grouping Analysis Task" entry
          (file+headline ,(expand-file-name "TODO.org" project-org-repo-root) "Unsorted")
          "* TODO %?\n  %U\n"))
        :agenda-custom-commands
        (("rx" "External RxP Task Grouping Analysis Tasks" tags-todo "TODO=\"TODO\""))))
