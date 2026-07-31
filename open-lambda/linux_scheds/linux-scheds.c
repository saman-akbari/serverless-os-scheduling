#include <ctype.h>
#include <dirent.h>
#include <sched.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/types.h>
#include <unistd.h>

#define MAX_PIDS_PER_FILE 128
#define SANDBOX_PRIO 49
#define OL_PRIO 50
#define SELF_PRIO 51

bool isDir(struct dirent *entry) {
    return (entry->d_type) == DT_DIR;
}

bool isRegularFile(struct dirent *entry) {
    return (entry->d_type) == DT_REG;
}

bool isEqual(struct dirent *entry, char *fname) {
    // printf("Comparing(%s, %s)\n", entry->d_name, fname);
    return strcmp(entry->d_name, fname) == 0;
}

bool isParentDir(struct dirent *entry) {
    return isEqual(entry, "..");
}

bool isCurrentDir(struct dirent *entry) {
    return isEqual(entry, ".");
}

bool isNumericDir(struct dirent *entry) {
    size_t length = strlen(entry->d_name);
    for(size_t i = 0; i < length; i++) {
        char currChar = entry->d_name[i];
        if(!isdigit(currChar))
            return false;
    }
    return true;
}

void join(char *dest, char *path1, char *path2) {
    strcat(dest, path1);
    strcat(dest, "/");
    strcat(dest, path2);
}

pid_t getPidFromDirname(struct dirent *piddir) {
    return strtol(piddir->d_name, (char **)NULL, 10);
}

void getPidsFromFile(char *fpath, pid_t *pids, u_int8_t *size) {
    FILE *fp;

    fp = fopen(fpath, "r");

    char line[256];
    while(fgets(line, sizeof line, fp) != NULL) {
        // allow only max pids per file
        if (*size >= MAX_PIDS_PER_FILE) {
            fprintf(stderr, "WARNING: getPidsFromFile supports only %d per file. Got more\n", MAX_PIDS_PER_FILE);
            break;
        }
        
        // parse pid
        pid_t pid = strtol(line, (char **)NULL, 10);

        // store pid
        pids[*size] = pid;
        *size += 1;
    }

    int res = fclose(fp);
    if(res != 0) {
        fprintf(stderr, "Failed to close file %s.\n", fpath);
    }
}

char *idtosched(int id) {
    if (id == SCHED_OTHER) return "SCHED_OTHER";
    if (id == SCHED_FIFO) return "SCHED_FIFO";
    if (id == SCHED_RR) return "SCHED_RR";
    if (id == -1) return "pid doesnt exist anymore";
    return "SCHED UNKNOWN";
}

bool isSchedFIFO(char *arg){
    return strcmp(arg, "SCHED_FIFO") == 0;
}

bool isSchedRR(char *arg){
    return strcmp(arg, "SCHED_RR") == 0;
}

bool isSchedOTHER(char *arg){
    return strcmp(arg, "SCHED_OTHER") == 0;
}

int schedtoid(char *name) {
    if (isSchedOTHER(name)) return SCHED_OTHER;
    if (isSchedFIFO(name)) return SCHED_FIFO;
    if (isSchedRR(name)) return SCHED_RR;
    return -1;
}

void printSchedInfo(pid_t pid) {
    int schedId = sched_getscheduler(pid);
    printf("policy-id=%d\n", schedId);
    printf("policy=%s\n", idtosched(schedId));
}

int updateSchedPolicy(pid_t pid, int targetSchedId, int prio) {
        struct sched_param sched_policy = { .sched_priority = prio };
        int result = sched_setscheduler(pid, targetSchedId, &sched_policy);
        
        if (result != 0) {
            fprintf(stderr, "Failed to update scheduler for pid=%d\n", pid);
            return 1;
        }

        printf("Successful scheduler update for pid=%d\n", pid);
        return 0;
}

void updateSchedPolicies(pid_t *pids, u_int8_t size, int targetSchedId, int prio) {
    //printf("Updating...\n");
    for(u_int8_t i = 0; i < size; i++) {
        // get current sched policy
        int currentSchedId = sched_getscheduler(pids[i]);

        // ignore pids where get failed
        if(currentSchedId == -1) {
            printf("WARNING: Failed to retrieve schedId for %ld\n", (long) pids[i]);
            continue;
        }
        // ignore pids where actual schedId matches expected
        if(currentSchedId == targetSchedId){
            printf("DEBUG: Skipping pid=%ld\n", (long) pids[i]);
            continue;
        }

        // update policy
        updateSchedPolicy(pids[i], targetSchedId, prio);
    }

    return;
}

int traverse(char *dir, int targetSchedId, int targetPrio) {
    DIR *dirp;
    struct dirent *entry;

    // open directory
    //printf("Opening %s\n", dir);
    dirp = opendir(dir);
    if (dirp == NULL) {
        fprintf(stderr, "Failed to open dir.\n");
        return 1;
    }

    // traverse through directory's contents
    while((entry = readdir(dirp)) != NULL){
        if(isDir(entry) && !isCurrentDir(entry) && !isParentDir(entry)){
            // traverse subdir
            char subPath[256] = {0};
            join(subPath, dir, entry->d_name);
            traverse(subPath, targetSchedId, targetPrio);
            continue;
        }

        if(isRegularFile(entry) && isEqual(entry, "cgroup.threads")) {
            // handle file containing ol pids
            char fpath[256] = {0};
            join(fpath, dir, entry->d_name);

            pid_t pids[MAX_PIDS_PER_FILE] = {0};
            u_int8_t size = 0;
            getPidsFromFile(fpath, pids, &size);
            updateSchedPolicies(pids, size, targetSchedId, targetPrio);
        }
        //printf("%s %s\n", type, entry->d_name);
    }

    // cleanup
    int result = closedir(dirp);
    if (result == -1) {
        fprintf(stderr, "Failed to close dir,\n");
        return 1;
    }

    return 0;
}

void updateSystemQuantum(u_int64_t targetQuantum) {
    FILE *fp;
    char *path = "/proc/sys/kernel/sched_rr_timeslice_ms";

    fp = fopen(path, "w");

    if(fp == NULL) {
        fprintf(stderr, "ERROR: Failed to open system quantum config file\n");
        exit(1);
    }

    char s[4];
    snprintf(s, 4, "%ld", targetQuantum);
    int res = fputs(s, fp);
    if(res == EOF) {
        fprintf(stderr, "ERROR: Failed to write system quantum config file\n");
        exit(1);
    }

    res = fclose(fp);
    if(res != 0) {
        fprintf(stderr, "ERROR: Failed to close system quantum config file\n");
        exit(1);
    }
}

void printWrongUsage(char *programName) {
    printf("Wrong Usage\n\n");
    printf("Usage: %s sched-name [quantum]\n", programName);
    printf("  sched-name  either SCHED_FIFO or SCHED_RR\n");
    printf("  quantum     set quantum size in ms for SCHED_RR from {1, 2, ..., 1000}\n");
}

bool isOlProcessDir(struct dirent *entry) {
    if(!isDir(entry) || isCurrentDir(entry) || isParentDir(entry) || !isNumericDir(entry))
        return false;

    // open comm file of pid dir
    char fpath[256] = {0};
    char tmp[256] = {0};
    join(tmp, "/proc", entry->d_name);
    join(fpath, tmp, "comm");

    FILE *fp = fopen(fpath, "r");
    if(fp == NULL) {
        fprintf(stderr, "X Failed to open %s\n", fpath);
        return false;
    }

    // check if comm = ol
    bool result = false;
    char line[256];
    while(fgets(line, sizeof line, fp) != NULL) {
        if(strcmp(line, "ol\n") == 0) {
            //printf("%s (%s)\n", line, fpath);
            result = true;
        }
    }

    // cleanup
    int res = fclose(fp);
    if(res != 0) {
        fprintf(stderr, "Failed to close file %s.\n", fpath);
    }

    return result;
}

pid_t getOLPid() {
    pid_t olPid = 0;
    char *dir= "/proc";

    DIR *dirp;
    struct dirent *entry;

    // open directory
    dirp = opendir(dir);
    if (dirp == NULL) {
        fprintf(stderr, "Failed to open dir.\n");
        return 1;
    }

    // traverse through /proc's contents
    while((entry = readdir(dirp)) != NULL){
        if(isOlProcessDir(entry)){
            if (olPid != 0) {
                printf("WARNING: Found more than one pid associated to ol\n");
                continue;
            }

            olPid = getPidFromDirname(entry);
        }
    }

    // cleanup
    int result = closedir(dirp);
    if (result == -1) {
        fprintf(stderr, "Failed to close dir,\n");
        return 1;
    }

    return olPid;
}

void getOLTaskIds(pid_t olPid, pid_t *pids, u_int8_t *size) {
    // convert pid to string
    char pid[64] = {0};
    sprintf(pid, "%d", olPid);

    char taskdir[256] = {0};
    strcat(taskdir, "/proc/");
    strcat(taskdir, pid);
    strcat(taskdir, "/task");

    DIR *dirp;
    struct dirent *entry;

    // open directory
    dirp = opendir(taskdir);
    if (dirp == NULL) {
        fprintf(stderr, "Failed to open dir.\n");
        return;
    }

    // print tasks
    while((entry = readdir(dirp)) != NULL){
        if(isDir(entry) && isNumericDir(entry)){
            //printf("  FOUND: %s\n", entry->d_name);
            pids[*size] = getPidFromDirname(entry);
            *size += 1;
            continue;
        }
    }

    // cleanup
    int result = closedir(dirp);
    if (result == -1) {
        fprintf(stderr, "Failed to close dir,\n");
    }

    return;
}

void updateOLTaskScheduling(int targetSchedId, int prio) {
    pid_t olPid = getOLPid();

    if(olPid == 0) {
        printf("Found no running OpenLambda instance...\n");
        return;
    }

    //printf("OL=%d\n", olPid);

    pid_t pids[MAX_PIDS_PER_FILE] = {0};
    u_int8_t size = 0;

    getOLTaskIds(olPid, pids, &size);

    // for(int i = 0; i < size; i++) {
    //     printf("  ol-tid=%d\n", pids[i]);
    // }

    updateSchedPolicies(pids, size, targetSchedId, prio);
}

void setupProgram(int schedId){
    pid_t me = getpid();

    int currentSchedId = sched_getscheduler(me);
    if (currentSchedId == -1) {
        fprintf(stderr, "ERROR: Failed to retrieve sched policy of running program.\n");
        exit(1);
    }

    int result = updateSchedPolicy(me, schedId, SELF_PRIO);

    if (result == -1){
        fprintf(stderr, "ERROR: Failed to update sched policy of running program.\n");
        exit(1);
    }

    currentSchedId = sched_getscheduler(me);
    if (currentSchedId == -1) {
        fprintf(stderr, "ERROR: Failed to retrieve sched policy of running program.\n");
        exit(1);
    }

    printf("DEBUG: pid=%lu uses %s\n", (long) me, idtosched(currentSchedId));
}

void startScheduling(int schedId) {
    while(true) {
        printf("Updating...\n");
        updateOLTaskScheduling(schedId, OL_PRIO);
        traverse("/sys/fs/cgroup/ol-sandboxes/", schedId, SANDBOX_PRIO);
        fflush(stdout);
        fflush(stderr);
        sleep(1);
    }
}

int main(int argc, char **argv) {
    // cli validation & parsing
    if( argc < 2 || argc > 3 || 
        schedtoid(argv[1]) == -1 ||
        (isSchedFIFO(argv[1]) && argc != 2) ||
        (isSchedRR(argv[1]) && argc != 3) ||
        isSchedOTHER(argv[1])
    ) {
        printWrongUsage(argv[0]);
        return 1;
    }

    char *schedName = argv[1];
    int schedId = schedtoid(schedName);
    
    // update system quantum for SCHED_RR
    if(isSchedRR(schedName)) {
        u_int64_t quantum = strtol(argv[2], NULL, 10); 
        //printf("QUANTUM: %lu\n", quantum);

        if(quantum < 1 || quantum > 1000) {
            printWrongUsage(argv[0]);
            return 1;
        }
        updateSystemQuantum(quantum);
    }

    // set sched policy of running program to same schedId but higher prio
    setupProgram(schedId);

    startScheduling(schedId);

    return 0;
}