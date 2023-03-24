## Branches

-   Branches should be named `feature/XXX--short-desc` or `hotfix/short-desc`, where "XXX" is the associated 
    Github project ticket.
    -   If a branch is not associated with a ticket, either it's a hotfix or it needs a ticket.
    -   Hotfixes should be used sparingly. For instance, a bug introduced in the same release cycle 
    (or discovered very shortly after merging a PR) can be hotfixed. Bugs that a user may have been exposed to should 
    be logged as tickets.

## Pull Requests

-   Pull requests should be made against `develop`, using the pull request template in `.github/pull_request_template.md`.
    
    -   GitHub will automatically populate a new PR with this template.
    -   Please fill out all information in the PR header, as well as any information in the subsections.
    -   Every PR should include a summary of changes that gives reviewers an idea of what they should pay attention to.
    -   Any unused or empty subsection may be removed.
-   PR branches should have as "clean" of a history as possible.
    -   Each commit should present one change or idea to a reviewer.
    -   Commits that merely "fix up" previous commits must be interactively rebased and squashed into their targets.
-   Prefer the use of `git rebase`.
    
    1.  `git rebase` `git rebase` actually _rebases_ your branch from the current development branch's endpoint. This 
    localizes conflicts to the commits at which they actually appear, though it can become complicated when there are 
    more than a few conflicts.
    2.  `git merge` `git merge` pulls in all the updates that your branch does not have, and combines them with the 
    updates you have made in a single merge commit. This allows you to deal with any and all conflicts at once, but 
    information such as when conflicts originated is lost.
    
    For more info on `git merge` vs `git rebase` see [here](https://www.atlassian.com/git/tutorials/merging-vs-rebasing).
    
-   Before merging a PR, the following requirements must be met. These requirements ensure that history is effectively 
linear, which aids readability and makes `git bisect` more useful and easier to reason about.
    
    -   At least one (perferably two) reviewers have approved the PR.
    -   No outstanding review comments have been left unresolved.
    -   The branch passes continuous integration.
    -   The branch has been rebased onto the current `develop` branch.
-   The "Squash and merge" and "Rebase and merge" buttons on GitHub's PR interface should not be used (They are 
disabled). Always use the "Merge" strategy.
    -   In combination with the restrictions above, this ensures that features are neatly bracketed by merge commits 
    on either side, making a clear hierarchical separation between features added to `develop` and the work that went 
    into each feature.

**tl;dr** All development should correspond to a Github ticket, and branch names and PRs should include the ticket name.

## Write-Ups About Good Commit/PR/Code Review Practice

The following three articles describe in greater detail the ideals to which this repository adheres.

-   [How to write a good commit message](https://chris.beams.io/posts/git-commit/)
-   [Telling Stories Through Your Commits](https://blog.mocoso.co.uk/talks/2015/01/12/telling-stories-through-your-commits/)
-   [How to Make Your Code Reviewer Fall in Love with You](https://mtlynch.io/code-review-love/)

# Coding Guidelines

## Motivation

Coding style is important. A clean, consistent style leads to code that
is more readable, debuggable, and maintainable. To this end, we
prescribe (and proscribe) a variety of practices. Our goal is to
encourage agile but reasoned development of code that can be easily
understood by others.

**C/C++ foundational guidelines**: this document uses as its foundation
the coding guidelines developed by Stroustrup and Sutter.

This foundational set of guidelines is extensive and
where the Ceilim document is silent these guidelines will prevail.

These are guidelines, not rules. With very few exceptions, this document
does not completely ban any particular C/C++ or Python pattern or
feature, but rather describes best practice, to be used in the large
majority of cases. When deviating from the guidelines given here, just
be sure to consider your options carefully, and to document your
reasoning, in the code.

Above all else, be consistent. Follow this guide whenever possible, but
if you are editing a package written by someone else, follow the
existing stylistic conventions in that package (unless you are
retrofitting the whole package to follow this guide, for which you
deserve an award).

## What about non-conforming code?

Some Basilisk code was written prior to the release (and updates) of
this style guide. Thus, the codebase may contain code that doesn’t
conform to this guide. The following advice is intended for the
developer working with non-conforming code:

1.  All new code should conform to this guide.
2.  Unless you have copious free time, don’t undertake converting the
    existing codebase to conform to this guide.
3.  If you are the author of a non-conforming package, try to find time
    to update the code to conform.
4.  If you are doing minor edits to non-conforming code, follow the
    existing stylistic conventions in that code (if any). Don’t mix
    styles.
5.  If you are doing major work on non-conforming code, take the
    opportunity to re-style it to conform to this guide.

## Naming

The following shortcuts are used in this document to denote naming
schemes:

-   CamelCased: The name starts with a capital letter, and has a capital
    letter for each new word, with no underscores.
-   camelCased: Like CamelCase, but with a lower-case first letter
-   under_scored: The name uses only lower-case letters, with words
    separated by underscores.
-   ALL_CAPITALS: All capital letters, with words separated by
    underscores.

## General Guidelines

### Variables

No single letter variables. The only exceptions are ‘i’ as an iteration
index and a select list of mathematical symbols.

### Naming Variable for Mathematics

The following section specifies general guidelines for the naming of
variable to be used in code which implements mathematical operations.
The naming convention is heavily influenced by the textbook [Analytical
Mechanics of Space
Systems](https://arc.aiaa.org/doi/book/10.2514/4.105210) by Schaub and
Junkins.

### Indicating Reference Frames

A vector variable expressed with components in a reference frame
$\\cal B$, is represented with the variable name followed by an
underscore and a capital letter denoting the frame ${}^{\\cal B}\\bf v$
as `vector_B`.

An angular rate variable expressed in one frame $\\cal B$ with respect
to a second $\\cal R$, where components are expressed in the frame
$\\cal B$, ${}^{\\cal B}\\pmb\\omega\_{\\mathcal{B}/\\mathcal{R}}$, is
given as `omega_BR_B`.

### MRP’s and DCM’s

A direction cosine matrix is expressed as \[*B**N*\], a mapping of an
$\\cal N$ frame vector into a $\\cal B$ frame vector, is written
`dcm_BN`. Similarly for the Modified Rodrigues Parameters (MRP) attitude
parameterization the **σ**<sub>ℬ/𝒩</sub> is written `sigma_BN`.

<div class="warning">

<div class="title">

Warning

</div>

If you are using the [Intel Eigen library](http://eigen.tuxfamily.org)
library to do linear algebra, the mapping from an attitude description
such as quaternions or MRPs to a direction cosine matrix (DCM) using
`.toRotationMatrix()` will return \[*N**B*\], not \[*B**N*\].

</div>

### Inertia Tensor

The Inertia tensor \[*I*<sub>*C*</sub>\] of the hub about the point *C*
is defined in the body frame $\\cal B$ components using the variable
`IHubPntC_B`.

### Derivatives

The first and second time derivatives of scalar (*ẋ*, $\\ddot{x}$) or
vector ($\\dot{\\bf{x}}$, $\\ddot{\\bf{x}}$) quantities, respectively
are written as `xDot` and `xDDot`.

The first and second time derivatives with respect to a variable other
than time should use the same pattern as time derivatives but with a
different modifier. For example, *f*′(*x*) and *f*″(*x*) are written as
`xPrime` and `xDPrime` respectively.

### Common Usage Examples

-   Position vector from $\\cal N$ to $\\cal B$ in inertial frame
    components ${}^{\\cal N} \\bf r\_{\\mathcal{B/N}}$: `r_BN_N`
-   Inertial time derivative of position vector from $\\cal N$ to
    $\\cal B$ in inertial frame components
    ${}^{\\cal N} \\dot{\\bf r}\_{\\cal B/N}$: `rDot_BN_N`
-   Time derivative with respect to the body of position vector from *B*
    to *H* in body frame components ${}^{\\cal B} \\bf r'\_{H/B}$:
    `rPrime_HB_B`
-   Unit direction vector from *B* to *S* in body frame components
    ${}^{\\cal B} \\hat{\\bf s}\_{S/B}$: `sHat_SB_B`
-   Inertial time derivative of body angular rate with respect to the
    inertial frame in body frame components
    ${}^{\\cal B} \\dot{\\pmb\\omega}\_{\\mathcal{B}/\\mathcal{N}}$:
    `omegaDot_BN_B`
-   DCM of the body frame with respect to the inertial frame \[*B**N*\]:
    `dcm_BN`


## Exceptions

-   Currently no exceptions
